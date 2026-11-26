"""Pont entre les canaux de messagerie et l'agent hébergé sur Claude Managed Agents.

- Une session principale et durable par utilisateur (un seul fil, comme Instinct), réinitialisable par /new.
- Chaque message ouvre d'abord un flux d'événements, puis envoie le message (« stream-first »).
- Les outils maison et les validations sont traités dès qu'ils apparaissent, et rattrapés en
  cas de flux coupé par le webhook Anthropic et par un sondage périodique.
- Chaque événement n'est traité qu'une fois (table claims), quel que soit le chemin qui le voit.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Iterable, Optional

import anthropic

from .channels import Channel
from .config import Settings
from .google_tools import Google
from .store import Store
from . import tools

log = logging.getLogger("instinct.bridge")

BETA = ["managed-agents-2026-04-01"]
WATCH_MAX_SECONDS = 45 * 60


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def message_text(event: Any) -> str:
    parts = []
    for block in _get(event, "content", []) or []:
        if _get(block, "type") == "text":
            parts.append(_get(block, "text", ""))
    return "\n".join(p for p in parts if p).strip()


class Bridge:
    def __init__(self, client: anthropic.Anthropic, store: Store, settings: Settings, channels: dict[str, Channel], google: Google):
        self.client = client
        self.store = store
        self.s = settings
        self.channels = channels
        self.google = google
        # Lance une tâche de fond ; remplacé par un appel direct dans les tests.
        self.spawn = lambda fn, *args: threading.Thread(target=fn, args=args, daemon=True).start()

    # ------------------------------------------------------------------ canaux
    def default_channel(self) -> str:
        """Canal qui reçoit les messages des tâches planifiées (une notification sur le téléphone)."""
        if self.s.default_channel in self.channels:
            return self.s.default_channel
        for name in ("telegram", "whatsapp", "app"):
            if name in self.channels:
                return name
        return ""

    def channel_for(self, session_id: str) -> Optional[Channel]:
        """Canal principal d'une session : celui où l'utilisateur a écrit en dernier."""
        name = self.default_channel()
        if session_id == self.store.get("main_session_id"):
            name = self.store.get("last_channel") or name
        return self.channels.get(name)

    def targets(self, session_id: str) -> list[Channel]:
        """Le canal principal, plus l'app qui garde tout l'historique."""
        out: list[Channel] = []
        for ch in (self.channel_for(session_id), self.channels.get("app")):
            if ch is not None and ch not in out:
                out.append(ch)
        return out

    def notify(self, session_id: str, text: str) -> None:
        if not text:
            return
        for ch in self.targets(session_id):
            ch.send_text(text)

    def record_user(self, channel: str, content: list[dict]) -> None:
        if "app" not in self.channels:
            return
        texts = [b.get("text", "") for b in content if b.get("type") == "text"]
        files = [b for b in content if b.get("type") in ("image", "document")]
        text = "\n".join(t for t in texts if t)
        if files:
            text = (text + "\n" if text else "") + f"[{len(files)} pièce(s) jointe(s)]"
        self.store.add_message("user", "text", text, channel=channel)

    # ---------------------------------------------------------------- sessions
    def session_resources(self) -> list[dict]:
        res: list[dict] = []
        if self.s.memory_store_id:
            res.append(
                {
                    "type": "memory_store",
                    "memory_store_id": self.s.memory_store_id,
                    "access": "read_write",
                    "instructions": "Mémoire durable de l'utilisateur. Lis profil.md et preferences.md en début de conversation.",
                }
            )
        if self.s.github_repo_url and self.s.github_token:
            res.append(
                {
                    "type": "github_repository",
                    "url": self.s.github_repo_url,
                    "authorization_token": self.s.github_token,
                    "checkout": {"type": "branch", "name": self.s.github_branch},
                }
            )
        return res

    def new_main_session(self) -> str:
        kwargs: dict[str, Any] = {
            "agent": self.s.agent_id,
            "environment_id": self.s.environment_id,
            "title": "Conversation principale",
            "resources": self.session_resources(),
            "metadata": {"role": "main"},
        }
        if self.s.session_budget_cents > 0:
            kwargs["budget"] = {"type": "limit", "max_list_cost": {"amount": str(self.s.session_budget_cents), "currency": "USD"}}
        session = self.client.beta.sessions.create(**kwargs)
        self.store.set("main_session_id", session.id)
        log.info("Nouvelle session principale %s : https://platform.claude.com/workspaces/%s/sessions/%s", session.id, self.s.workspace, session.id)
        return session.id

    def main_session(self) -> str:
        return self.store.get("main_session_id") or self.new_main_session()

    def is_ours(self, session_id: str) -> bool:
        if session_id == self.store.get("main_session_id"):
            return True
        try:
            session = self.client.beta.sessions.retrieve(session_id)
        except anthropic.NotFoundError:
            return False
        return _get(_get(session, "agent"), "id") == self.s.agent_id

    # ------------------------------------------------------- messages entrants
    def handle_user_input(self, channel: str, content: list[dict], text_for_approval: str = "") -> None:
        """Point d'entrée de tout message de l'utilisateur (texte, image, document)."""
        self.store.set("last_channel", channel)
        self.record_user(channel, content)
        open_items = self.live_pending()
        if open_items and text_for_approval:
            item = open_items[0]
            choice = tools.parse_reply(text_for_approval, len(item["options"]))
            self.resolve(item["id"], choice, free_text=text_for_approval)
            return
        if open_items:
            # Une validation attend : on la règle avec le message de l'utilisateur pour que rien ne reste bloqué.
            self.resolve(open_items[0]["id"], None, free_text="(l'utilisateur a envoyé un fichier ou une image)")
        self.send_to_agent(content)

    def live_pending(self, max_age_hours: float = 12) -> list[dict]:
        """Validations encore ouvertes ; celles qui ont plus de 12 h sont abandonnées pour ne rien bloquer."""
        alive = []
        for item in self.store.open_pending():
            if time.time() - (item.get("at") or 0) > max_age_hours * 3600:
                self.store.close_pending(item["id"], "expired")
            else:
                alive.append(item)
        return alive

    def reset(self) -> None:
        """/new : nouvelle conversation (la mémoire durable est conservée)."""
        for item in self.store.open_pending():
            self.store.close_pending(item["id"], "cancelled")
        self.store.delete("main_session_id")

    def send_to_agent(self, content: list[dict], retry: bool = True) -> None:
        sid = self.main_session()
        try:
            self._send_with_watch(sid, [{"type": "user.message", "content": content}])
        except anthropic.NotFoundError:
            if retry:
                self.store.delete("main_session_id")
                self.send_to_agent(content, retry=False)
        except anthropic.BadRequestError as e:
            msg = str(e)
            if retry and ("terminated" in msg or "archived" in msg):
                self.store.delete("main_session_id")
                self.send_to_agent(content, retry=False)
            elif "budget" in msg:
                self.notify(sid, "Le budget de cette conversation est atteint. Envoie /new pour repartir sur une nouvelle conversation.")
            else:
                log.warning("Message refusé par la session %s : %s", sid, msg)
                self.process_idle(sid)
                self.notify(sid, "Je termine d'abord l'action en cours. Réponds à la question ci-dessus, puis renvoie ton message.")

    def interrupt(self) -> None:
        sid = self.store.get("main_session_id")
        if sid:
            self.client.beta.sessions.events.send(session_id=sid, events=[{"type": "user.interrupt"}])

    # ------------------------------------------------------- flux d'événements
    def _send_with_watch(self, session_id: str, events: list[dict]) -> None:
        ready = threading.Event()
        self.spawn(self._watch, session_id, ready)
        ready.wait(timeout=10)
        self.client.beta.sessions.events.send(session_id=session_id, events=events)

    def watch(self, session_id: str) -> None:
        """Suit une session déjà lancée (ex. tâche planifiée) jusqu'à sa prochaine pause."""
        self.spawn(self._watch, session_id, None)

    def _watch(self, session_id: str, ready: Optional[threading.Event]) -> None:
        started = time.monotonic()
        try:
            with self.client.beta.sessions.events.stream(session_id=session_id) as stream:
                if ready:
                    ready.set()
                seen_running = ready is None
                for event in stream:
                    etype = _get(event, "type")
                    if etype == "session.status_running":
                        seen_running = True
                    self.handle_event(session_id, event)
                    if etype == "session.status_terminated":
                        break
                    if etype == "session.status_idle" and seen_running:
                        break
                    if time.monotonic() - started > WATCH_MAX_SECONDS:
                        break
        except Exception:  # le flux peut couper : le rattrapage passe par process_idle
            log.exception("Flux interrompu pour %s", session_id)
        finally:
            if ready:
                ready.set()
        self.process_idle(session_id)

    def handle_event(self, session_id: str, event: Any) -> None:
        etype = _get(event, "type")
        eid = _get(event, "id")
        if not eid:
            return
        if etype == "agent.message":
            text = message_text(event)
            if text and self.store.claim(eid, "message"):
                self.notify(session_id, text)
        elif etype == "agent.custom_tool_use":
            self.handle_custom_tool(session_id, event)
        elif etype in ("agent.tool_use", "agent.mcp_tool_use") and _get(event, "evaluated_permission") == "ask":
            self.ask_confirmation(session_id, event)
        elif etype == "agent.thinking":
            ch = self.channel_for(session_id)
            if ch:
                ch.typing()

    # ---------------------------------------------- rattrapage à chaque pause
    def recent_events(self, session_id: str, limit: int = 100) -> list[Any]:
        page = self.client.beta.sessions.events.list(session_id=session_id, order="desc", limit=limit)
        data = list(_get(page, "data", []) or [])
        data.reverse()
        return data

    def process_idle(self, session_id: str) -> None:
        """Traite tout ce qui n'a pas encore été traité dans une session en pause."""
        try:
            events = self.recent_events(session_id)
        except Exception:
            log.exception("Impossible de lire les événements de %s", session_id)
            return
        by_id = {_get(e, "id"): e for e in events}
        last_idle = None
        for event in events:
            etype = _get(event, "type")
            if etype == "agent.message":
                self.handle_event(session_id, event)
            elif etype == "session.status_idle":
                last_idle = event
        if last_idle is None:
            return
        reason = _get(last_idle, "stop_reason")
        rtype = _get(reason, "type")
        if rtype == "requires_action":
            for eid in _get(reason, "event_ids", []) or []:
                ev = by_id.get(eid)
                if ev is not None:
                    self.handle_event(session_id, ev)
            return
        if rtype in ("retries_exhausted", "refusal", "budget_reached") and self.store.claim(_get(last_idle, "id"), "idle"):
            self.notify(
                session_id,
                {
                    "retries_exhausted": "Je n'ai pas réussi à terminer, suite à une erreur technique. Tu peux réessayer ou reformuler.",
                    "refusal": "Je ne peux pas aider sur cette demande.",
                    "budget_reached": "Le budget de cette conversation est atteint. Envoie /new pour en démarrer une nouvelle.",
                }[rtype],
            )
        self.deliver_files(session_id)

    def deliver_files(self, session_id: str) -> None:
        targets = self.targets(session_id)
        if not targets:
            return
        try:
            files = self.client.beta.files.list(scope_id=session_id, betas=BETA)
        except Exception:
            log.exception("Liste des fichiers impossible pour %s", session_id)
            return
        for f in _get(files, "data", []) or []:
            fid = _get(f, "id")
            if not fid or not self.store.claim(f"file:{fid}", "file"):
                continue
            try:
                data = self.client.files.download(fid).read()
                for ch in targets:
                    ch.send_file(_get(f, "filename", "fichier"), data)
            except Exception:
                log.exception("Envoi du fichier %s impossible", fid)

    # ------------------------------------------------------ outils et accords
    def handle_custom_tool(self, session_id: str, event: Any) -> None:
        eid = _get(event, "id")
        if self.store.is_claimed(eid):
            return
        name = _get(event, "name", "")
        data = dict(_get(event, "input", {}) or {})
        if not self.store.claim(eid, "tool"):
            return
        if name in tools.NEEDS_APPROVAL:
            text, options = tools.approval_prompt(name, data)
            self._ask(session_id, eid, "custom", name, data, text, options)
            return
        if name in tools.PRESENTATION:
            try:
                kind, card, result = tools.presentation_card(name, data)
            except tools.ToolError as e:
                self._send_tool_result(session_id, eid, {"erreur": str(e)}, True)
                return
            for ch in self.targets(session_id):
                ch.send_card(kind, card)
            self._send_tool_result(session_id, eid, result, False)
            return
        self._send_tool_result(session_id, eid, *self._run(name, data))

    def _ask(self, session_id: str, event_id: str, kind: str, name: str, data: dict, text: str, options: list[str]) -> None:
        primary = self.channel_for(session_id)
        pid = self.store.add_pending(session_id, event_id, kind, name, data, options, primary.name if primary else "")
        if not pid:
            return
        for ch in self.targets(session_id):
            ch.send_choices(text, options, pid)

    def _run(self, name: str, data: dict) -> tuple[Any, bool]:
        try:
            return tools.execute(name, data, self.google), False
        except tools.ToolError as e:
            return {"erreur": str(e)}, True

    def _send_tool_result(self, session_id: str, event_id: str, result: Any, is_error: bool) -> None:
        payload = json.dumps(result, ensure_ascii=False, default=str)
        self._send_with_watch(
            session_id,
            [
                {
                    "type": "user.custom_tool_result",
                    "custom_tool_use_id": event_id,
                    "content": [{"type": "text", "text": payload}],
                    "is_error": is_error,
                }
            ],
        )

    def ask_confirmation(self, session_id: str, event: Any) -> None:
        eid = _get(event, "id")
        if not self.store.claim(eid, "confirm"):
            return
        name = _get(event, "name", "outil")
        data = dict(_get(event, "input", {}) or {})
        text, options = tools.confirmation_prompt(name, data)
        self._ask(session_id, eid, "confirm", name, data, text, options)

    def resolve(self, pending_id: str, choice: Optional[int], free_text: str = "") -> str:
        """Applique la réponse de l'utilisateur à une validation. Renvoie un court accusé de réception."""
        item = self.store.get_pending(pending_id)
        if not item or not self.store.close_pending(pending_id, "done"):
            return "Déjà traité."
        sid, eid = item["session_id"], item["event_id"]
        if item["kind"] == "confirm":
            allow = choice == 0
            event: dict[str, Any] = {"type": "user.tool_confirmation", "tool_use_id": eid, "result": "allow" if allow else "deny"}
            if not allow:
                event["deny_message"] = free_text or "L'utilisateur a bloqué cette action."
            self._send_with_watch(sid, [event])
            return "Autorisé." if allow else "Bloqué."
        result: Any
        is_error = False
        try:
            result = tools.result_after_decision(item["tool_name"], item["input"], item["options"], choice, free_text, self.google)
        except tools.ToolError as e:
            result, is_error = {"erreur": str(e)}, True
        self._send_tool_result(sid, eid, result, is_error)
        if choice is None:
            return "Noté."
        return item["options"][choice] if 0 <= choice < len(item["options"]) else "Noté."

    # ----------------------------------------------------------------- Siri
    def ask_and_wait(self, text: str, timeout: float = 25.0) -> str:
        """Envoie une demande et attend la première réponse de l'agent (pour que Siri la lise)."""
        before = self.store.last_message_id()
        self.handle_user_input("app", [{"type": "text", "text": text}], text_for_approval=text)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for m in self.store.messages_after(before, 20):
                if m["role"] != "agent":
                    continue
                if m["kind"] == "text" and m["text"]:
                    return m["text"]
                if m["kind"] == "choices":
                    return m["text"] + " Réponds dans l'app."
                if m["kind"] in ("whatsapp", "options"):
                    return "C'est prêt, regarde dans l'app."
            time.sleep(0.7)
        return "Je m'en occupe, je te réponds dans l'app."

    # --------------------------------------------------------- sondage de secours
    def poll_once(self) -> None:
        sessions: Iterable[Any] = []
        try:
            page = self.client.beta.sessions.list(agent_id=self.s.agent_id, statuses=["idle"], limit=10, order="desc")
            sessions = _get(page, "data", []) or []
        except Exception:
            log.exception("Sondage des sessions impossible")
        for session in sessions:
            self.process_idle(_get(session, "id"))

    def poll_forever(self) -> None:
        while True:
            time.sleep(max(15, self.s.poll_seconds))
            self.poll_once()
