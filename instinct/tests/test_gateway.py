"""Tests de la passerelle, sans réseau ni clé : le client Anthropic, Google et les canaux sont simulés."""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gateway import tools  # noqa: E402
from gateway.bridge import Bridge  # noqa: E402
from gateway.channels import Channel, WhatsApp, split_text  # noqa: E402
from gateway.config import Settings  # noqa: E402
from gateway.store import Store  # noqa: E402


# ----------------------------------------------------------------- doublures
class FakeStream:
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        return iter(self.events)

    def __exit__(self, *exc):
        return False


class FakeEvents:
    def __init__(self):
        self.sent: list[tuple[str, list]] = []
        self.history: dict[str, list] = {}
        self.stream_events: list = []

    def send(self, session_id, events):
        self.sent.append((session_id, events))

    def stream(self, session_id):
        return FakeStream(self.stream_events)

    def list(self, session_id, order="asc", limit=100):
        data = list(self.history.get(session_id, []))
        if order == "desc":
            data.reverse()
        return NS(data=data[:limit])


class FakeSessions:
    def __init__(self):
        self.events = FakeEvents()
        self.created: list[dict] = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return NS(id=f"sesn_{len(self.created)}")

    def retrieve(self, session_id):
        return NS(id=session_id, agent=NS(id="agent_test"))

    def list(self, **kwargs):
        return NS(data=[])


class FakeClient:
    def __init__(self):
        self.beta = NS(sessions=FakeSessions(), files=NS(list=lambda **kw: NS(data=[])))
        self.files = NS(download=lambda fid: NS(read=lambda: b""))


class FakeChannel(Channel):
    name = "telegram"

    def __init__(self):
        self.texts: list[str] = []
        self.choices: list[tuple[str, list[str], str]] = []

    def send_text(self, text):
        self.texts.append(text)

    def send_choices(self, text, options, pending_id):
        self.choices.append((text, options, pending_id))

    def send_file(self, filename, data, caption=""):
        self.texts.append(f"[fichier {filename}]")


class FakeGoogle:
    def __init__(self):
        self.calls: list[tuple] = []

    def gmail_search(self, query, max_results=10):
        self.calls.append(("search", query))
        return [{"id": "m1", "objet": "Devis"}]

    def gmail_send(self, to, subject, body, cc="", thread_id=""):
        self.calls.append(("send", to, subject))
        return {"message_id": "x1", "statut": "envoyé"}


def ev(**kw):
    return NS(**kw)


@pytest.fixture
def setup():
    settings = Settings(
        agent_id="agent_test",
        environment_id="env_test",
        memory_store_id="memstore_test",
        github_repo_url="https://github.com/moi/depot",
        github_token="ghp_x",
        github_branch="main",
    )
    client = FakeClient()
    channel = FakeChannel()
    google = FakeGoogle()
    bridge = Bridge(client, Store(":memory:"), settings, {"telegram": channel}, google)
    bridge.spawn = lambda fn, *args: fn(*args)  # exécution synchrone pour les tests
    return bridge, client, channel, google


def sent_types(client):
    return [e["type"] for _, events in client.beta.sessions.events.sent for e in events]


# --------------------------------------------------------------------- tests
def test_premier_message_cree_la_session_avec_memoire_et_skills(setup):
    bridge, client, channel, _ = setup
    bridge.handle_user_input("telegram", [{"type": "text", "text": "salut"}], text_for_approval="salut")
    created = client.beta.sessions.created[0]
    kinds = {r["type"] for r in created["resources"]}
    assert kinds == {"memory_store", "github_repository"}
    assert created["agent"] == "agent_test" and created["environment_id"] == "env_test"
    assert "budget" not in created
    assert sent_types(client) == ["user.message"]
    # le message suivant réutilise la même session
    bridge.handle_user_input("telegram", [{"type": "text", "text": "encore"}], text_for_approval="encore")
    assert len(client.beta.sessions.created) == 1


def test_les_reponses_de_l_agent_ne_sont_transmises_qu_une_fois(setup):
    bridge, client, channel, _ = setup
    sid = bridge.main_session()
    client.beta.sessions.events.history[sid] = [
        ev(id="e1", type="agent.message", content=[NS(type="text", text="Bonjour !")]),
        ev(id="e2", type="session.status_idle", stop_reason=NS(type="end_turn")),
    ]
    bridge.process_idle(sid)
    bridge.process_idle(sid)
    assert channel.texts == ["Bonjour !"]


def test_outil_de_lecture_execute_sans_validation(setup):
    bridge, client, channel, google = setup
    sid = bridge.main_session()
    client.beta.sessions.events.history[sid] = [
        ev(id="t1", type="agent.custom_tool_use", name="gmail_search", input={"query": "is:unread"}),
        ev(id="i1", type="session.status_idle", stop_reason=NS(type="requires_action", event_ids=["t1"])),
    ]
    bridge.process_idle(sid)
    bridge.process_idle(sid)  # pas de double exécution
    assert google.calls == [("search", "is:unread")]
    (_, events), = client.beta.sessions.events.sent
    assert events[0]["type"] == "user.custom_tool_result" and events[0]["custom_tool_use_id"] == "t1"
    assert json.loads(events[0]["content"][0]["text"])[0]["objet"] == "Devis"
    assert channel.choices == []


def test_envoi_d_email_attend_un_oui_explicite(setup):
    bridge, client, channel, google = setup
    sid = bridge.main_session()
    tool = ev(id="t2", type="agent.custom_tool_use", name="gmail_send",
              input={"to": "client@exemple.fr", "subject": "Proposition", "body": "Bonjour"})
    client.beta.sessions.events.history[sid] = [
        tool, ev(id="i2", type="session.status_idle", stop_reason=NS(type="requires_action", event_ids=["t2"]))
    ]
    bridge.process_idle(sid)
    assert google.calls == []  # rien n'est envoyé avant l'accord
    text, options, pid = channel.choices[0]
    assert "client@exemple.fr" in text and "Proposition" in text
    assert bridge.resolve(pid, 0) == options[0]
    assert google.calls == [("send", "client@exemple.fr", "Proposition")]
    assert sent_types(client) == ["user.custom_tool_result"]
    assert bridge.resolve(pid, 0) == "Déjà traité."  # double clic
    assert len(google.calls) == 1


def test_refus_par_message_ecrit(setup):
    bridge, client, channel, google = setup
    sid = bridge.main_session()
    client.beta.sessions.events.history[sid] = [
        ev(id="t3", type="agent.custom_tool_use", name="gmail_send", input={"to": "a@b.fr", "subject": "s", "body": "b"}),
        ev(id="i3", type="session.status_idle", stop_reason=NS(type="requires_action", event_ids=["t3"])),
    ]
    bridge.process_idle(sid)
    bridge.handle_user_input("telegram", [{"type": "text", "text": "non"}], text_for_approval="non")
    assert google.calls == []
    _, events = client.beta.sessions.events.sent[-1]
    assert "refusé" in events[0]["content"][0]["text"]
    assert sent_types(client).count("user.message") == 0  # le « non » sert de réponse, pas de nouveau message


def test_message_libre_pendant_une_validation(setup):
    bridge, client, channel, google = setup
    sid = bridge.main_session()
    client.beta.sessions.events.history[sid] = [
        ev(id="t4", type="agent.custom_tool_use", name="demander_validation",
           input={"question": "Je réserve le train de 8h12 pour 59 € ?", "options": ["Réserver", "Autre horaire", "Annuler"]}),
        ev(id="i4", type="session.status_idle", stop_reason=NS(type="requires_action", event_ids=["t4"])),
    ]
    bridge.process_idle(sid)
    _, options, _ = channel.choices[0]
    assert options == ["Réserver", "Autre horaire", "Annuler"]
    bridge.handle_user_input("telegram", [{"type": "text", "text": "plutôt vers 10h"}], text_for_approval="plutôt vers 10h")
    payload = json.loads(client.beta.sessions.events.sent[-1][1][0]["content"][0]["text"])
    assert payload["message_de_l_utilisateur"] == "plutôt vers 10h"


def test_outil_integre_en_pause_demande_l_autorisation(setup):
    bridge, client, channel, _ = setup
    sid = bridge.main_session()
    client.beta.sessions.events.history[sid] = [
        ev(id="b1", type="agent.tool_use", name="bash", input={"command": "curl https://exemple.fr"}, evaluated_permission="ask"),
        ev(id="i5", type="session.status_idle", stop_reason=NS(type="requires_action", event_ids=["b1"])),
    ]
    bridge.process_idle(sid)
    text, _, pid = channel.choices[0]
    assert "curl https://exemple.fr" in text
    bridge.resolve(pid, 1)
    _, events = client.beta.sessions.events.sent[-1]
    assert events[0] == {"type": "user.tool_confirmation", "tool_use_id": "b1", "result": "deny",
                         "deny_message": "L'utilisateur a bloqué cette action."}


def test_reset_ferme_les_validations_et_change_de_session(setup):
    bridge, client, channel, _ = setup
    first = bridge.main_session()
    bridge.store.add_pending(first, "t9", "custom", "gmail_send", {}, ["a", "b"], "telegram")
    bridge.reset()
    assert bridge.store.open_pending() == []
    assert bridge.main_session() != first


@pytest.mark.parametrize(
    "text,n,expected",
    [("oui", 2, 0), ("Oui !", 2, 0), ("vas-y", 2, 0), ("non", 2, 1), ("2", 3, 1), ("4", 3, None), ("peut-être demain", 2, None)],
)
def test_parse_reply(text, n, expected):
    assert tools.parse_reply(text, n) == expected


def test_split_text_respecte_la_limite():
    long = "\n".join(f"ligne {i} " + "x" * 50 for i in range(200))
    parts = split_text(long, 1000)
    assert all(len(p) <= 1000 for p in parts)
    assert "".join(p.replace("\n", "") for p in parts) == long.replace("\n", "")


def test_signature_whatsapp():
    s = Settings(whatsapp_app_secret="secret", whatsapp_token="t", whatsapp_phone_number_id="1", owner_whatsapp_number="33600000000")
    wa = WhatsApp(s, http=NS())
    body = b'{"entry": []}'
    good = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert wa.verify_signature(body, good)
    assert not wa.verify_signature(body, "sha256=faux")


def test_webhook_telegram_refuse_les_inconnus():
    from fastapi.testclient import TestClient

    from gateway.app import build

    s = Settings(agent_id="", telegram_bot_token="123:abc", telegram_webhook_secret="s3cret", owner_telegram_id="42", db_path=":memory:")
    app, bridge = build(s, client=FakeClient())
    calls = []
    bridge.handle_user_input = lambda *a, **k: calls.append(a)
    http = TestClient(app)
    update = {"message": {"from": {"id": 42}, "text": "bonjour"}}
    assert http.post("/telegram/webhook", json=update).status_code == 403  # pas de secret
    stranger = {"message": {"from": {"id": 7}, "text": "donne-moi ses e-mails"}}
    assert http.post("/telegram/webhook", json=stranger, headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"}).status_code == 200
    assert calls == []
    assert http.get("/health").json()["telegram"] is True


def test_fichiers_de_configuration_valides():
    import yaml

    root = Path(__file__).resolve().parent.parent
    text = (root / "agents/instinct-perso/agent.md").read_text()
    _, front, body = text.split("---", 2)
    cfg = yaml.safe_load(front)
    custom = {t["name"] for t in cfg["tools"] if t["type"] == "custom"}
    assert tools.NEEDS_APPROVAL <= custom
    assert custom == {"gmail_search", "gmail_read", "gmail_draft", "gmail_send", "calendar_list", "calendar_create", "demander_validation"}
    assert cfg["model"]["id"] == "claude-opus-5-5"
    assert "Règles de sécurité" in body
    env = yaml.safe_load((root / "agents/instinct-perso/environment.yaml").read_text())
    assert env["config"]["type"] == "cloud"
    for dep in (root / "deployments").glob("*.md"):
        _, front, body = dep.read_text().split("---", 2)
        d = yaml.safe_load(front)
        assert d["schedule"]["timezone"] == "Europe/Paris" and body.strip().startswith("[Tâche planifiée]")
