"""Crée ou met à jour l'agent chez Anthropic (à lancer une fois, puis à chaque modification).

    python scripts/provision.py --dry-run   # affiche ce qui serait fait
    python scripts/provision.py             # applique

Ce que fait le script, dans l'ordre :
1. l'environnement (agents/instinct-perso/environment.yaml)
2. la mémoire durable (memory_stores/memoire.yaml) et ses fichiers de départ (memory_seed/)
3. l'agent (agents/instinct-perso/agent.md) : une modification crée une nouvelle version
4. les tâches planifiées (deployments/*.md)
5. le webhook Telegram, si TELEGRAM_BOT_TOKEN et PUBLIC_BASE_URL sont définis

Les identifiants créés sont enregistrés dans state.json (pas de secret dedans).
Variables lues : ANTHROPIC_API_KEY, GITHUB_REPO_URL, GITHUB_TOKEN, GITHUB_BRANCH,
DEPLOYMENT_BUDGET_CENTS, TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, PUBLIC_BASE_URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATE_FILE = ROOT / "state.json"
AGENT_FILE = ROOT / "agents" / "instinct-perso" / "agent.md"
ENV_FILE = ROOT / "agents" / "instinct-perso" / "environment.yaml"
MEMORY_FILE = ROOT / "memory_stores" / "memoire.yaml"
SEED_DIR = ROOT / "memory_seed"
DEPLOY_DIR = ROOT / "deployments"


def read_front_matter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise SystemExit(f"{path} : en-tête YAML manquant")
    _, front, body = text.split("---", 2)
    return yaml.safe_load(front) or {}, body.strip()


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def session_resources(memory_store_id: str) -> list[dict]:
    res = [
        {
            "type": "memory_store",
            "memory_store_id": memory_store_id,
            "access": "read_write",
            "instructions": "Mémoire durable de l'utilisateur, partagée avec la conversation principale.",
        }
    ]
    repo, token = os.environ.get("GITHUB_REPO_URL", ""), os.environ.get("GITHUB_TOKEN", "")
    if repo and token:
        res.append(
            {
                "type": "github_repository",
                "url": repo,
                "authorization_token": token,
                "checkout": {"type": "branch", "name": os.environ.get("GITHUB_BRANCH", "main")},
            }
        )
    else:
        print("  ! GITHUB_REPO_URL ou GITHUB_TOKEN absent : les tâches planifiées n'auront pas les skills du dépôt.")
    return res


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="n'appelle pas l'API, affiche seulement le plan")
    parser.add_argument("--skip-deployments", action="store_true", help="ne crée pas les tâches planifiées")
    args = parser.parse_args()

    state = load_state()
    agent_cfg, system_prompt = read_front_matter(AGENT_FILE)
    env_cfg = yaml.safe_load(ENV_FILE.read_text(encoding="utf-8"))
    mem_cfg = yaml.safe_load(MEMORY_FILE.read_text(encoding="utf-8"))
    deployments = [read_front_matter(p) + (p.stem,) for p in sorted(DEPLOY_DIR.glob("*.md"))]

    if args.dry_run:
        print("Plan :")
        print(f"  environnement  {'mise à jour' if state.get('environment_id') else 'création'} : {env_cfg['name']}")
        print(f"  mémoire        {'existante' if state.get('memory_store_id') else 'création'} : {mem_cfg['name']}"
              f" + {len(list(SEED_DIR.rglob('*.md')))} fichiers de départ")
        print(f"  agent          {'mise à jour' if state.get('agent_id') else 'création'} : {agent_cfg['name']}"
              f" ({len(agent_cfg.get('tools', []))} outils, {len(agent_cfg.get('skills', []))} skills Anthropic)")
        for cfg, _, stem in deployments:
            known = stem in state.get("deployments", {})
            print(f"  tâche planifiée {'mise à jour' if known else 'création'} : {cfg['name']} ({cfg['schedule']['expression']})")
        return

    import anthropic

    client = anthropic.Anthropic()

    # 1. Environnement
    if state.get("environment_id"):
        client.beta.environments.update(state["environment_id"], name=env_cfg["name"], config=env_cfg["config"],
                                        description=env_cfg.get("description"))
        print(f"Environnement mis à jour : {state['environment_id']}")
    else:
        env = client.beta.environments.create(name=env_cfg["name"], config=env_cfg["config"], description=env_cfg.get("description"))
        state["environment_id"] = env.id
        save_state(state)
        print(f"Environnement créé : {env.id}")

    # 2. Mémoire durable
    if not state.get("memory_store_id"):
        store = client.beta.memory_stores.create(name=mem_cfg["name"], description=mem_cfg["description"])
        state["memory_store_id"] = store.id
        save_state(state)
        print(f"Mémoire créée : {store.id}")
    for f in sorted(SEED_DIR.rglob("*.md")):
        path = "/" + f.relative_to(SEED_DIR).as_posix()
        try:
            client.beta.memory_stores.memories.create(state["memory_store_id"], path=path, content=f.read_text(encoding="utf-8"))
            print(f"  mémoire : {path} ajouté")
        except anthropic.ConflictError:
            pass  # déjà présent : on ne remplace jamais ce que l'agent a appris

    # 3. Agent
    fields = {k: agent_cfg[k] for k in ("name", "description", "model", "tools", "skills", "mcp_servers") if k in agent_cfg}
    fields["system"] = system_prompt
    if state.get("agent_id"):
        agent = client.beta.agents.update(state["agent_id"], **fields)
        print(f"Agent mis à jour : {agent.id} (version {agent.version})")
    else:
        agent = client.beta.agents.create(**fields)
        print(f"Agent créé : {agent.id} (version {agent.version})")
    state["agent_id"], state["agent_version"] = agent.id, agent.version
    save_state(state)

    # 4. Tâches planifiées
    if not args.skip_deployments:
        budget_cents = int(os.environ.get("DEPLOYMENT_BUDGET_CENTS", "200") or 0)
        resources = session_resources(state["memory_store_id"])
        state.setdefault("deployments", {})
        for cfg, body, stem in deployments:
            payload = {
                "name": cfg["name"],
                "agent": agent.id,
                "environment_id": state["environment_id"],
                "initial_events": [{"type": "user.message", "content": [{"type": "text", "text": body}]}],
                "schedule": cfg["schedule"],
                "resources": resources,
            }
            if budget_cents > 0:
                payload["budget"] = {"type": "limit", "max_list_cost": {"amount": str(budget_cents), "currency": "USD"}}
            dep_id = state["deployments"].get(stem)
            if dep_id:
                dep = client.beta.deployments.update(dep_id, **payload)
                print(f"Tâche planifiée mise à jour : {cfg['name']} ({dep.id})")
            else:
                dep = client.beta.deployments.create(**payload)
                state["deployments"][stem] = dep.id
                save_state(state)
                print(f"Tâche planifiée créée : {cfg['name']} ({dep.id})")
            upcoming = getattr(getattr(dep, "schedule", None), "upcoming_runs_at", None)
            if upcoming:
                print(f"  prochains passages (UTC) : {', '.join(str(u) for u in upcoming[:3])}")

    # 5. Webhook Telegram
    token, base = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if token and base:
        from gateway.channels import Telegram
        from gateway.config import load_settings

        result = Telegram(load_settings()).set_webhook(f"{base}/telegram/webhook")
        print(f"Webhook Telegram : {'OK' if result.get('ok') else result}")

    print("\nÀ mettre dans les variables d'environnement de la passerelle :")
    print(f"  AGENT_ID={state['agent_id']}")
    print(f"  ENVIRONMENT_ID={state['environment_id']}")
    print(f"  MEMORY_STORE_ID={state['memory_store_id']}")


if __name__ == "__main__":
    main()
