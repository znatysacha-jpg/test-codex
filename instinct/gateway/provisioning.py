"""Crée ou met à jour l'agent chez Anthropic à partir des fichiers du dépôt.

Utilisé par scripts/provision.py (en ligne de commande) et par la passerelle à chaque
démarrage (AUTO_PROVISION=1, par défaut) : déployer la passerelle suffit donc à créer
l'agent, son conteneur, sa mémoire et ses tâches planifiées, puis à les tenir à jour.
Les identifiants obtenus sont gardés dans state.json (pas de secret dedans).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
AGENT_FILE = ROOT / "agents" / "instinct-perso" / "agent.md"
ENV_FILE = ROOT / "agents" / "instinct-perso" / "environment.yaml"
MEMORY_FILE = ROOT / "memory_stores" / "memoire.yaml"
SEED_DIR = ROOT / "memory_seed"
DEPLOY_DIR = ROOT / "deployments"


def read_front_matter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path} : en-tête YAML manquant")
    _, front, body = text.split("---", 2)
    return yaml.safe_load(front) or {}, body.strip()


def load_state(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def session_resources(memory_store_id: str, repo_url: str, repo_token: str, branch: str) -> list[dict]:
    res: list[dict] = [
        {
            "type": "memory_store",
            "memory_store_id": memory_store_id,
            "access": "read_write",
            "instructions": "Mémoire durable de l'utilisateur, partagée avec la conversation principale.",
        }
    ]
    if repo_url and repo_token:
        res.append(
            {"type": "github_repository", "url": repo_url, "authorization_token": repo_token, "checkout": {"type": "branch", "name": branch}}
        )
    return res


def plan(state: dict) -> list[str]:
    agent_cfg, _ = read_front_matter(AGENT_FILE)
    env_cfg = yaml.safe_load(ENV_FILE.read_text(encoding="utf-8"))
    mem_cfg = yaml.safe_load(MEMORY_FILE.read_text(encoding="utf-8"))
    lines = [
        f"environnement  {'mise à jour' if state.get('environment_id') else 'création'} : {env_cfg['name']} (réseau {env_cfg['config']['networking']['type']})",
        f"mémoire        {'existante' if state.get('memory_store_id') else 'création'} : {mem_cfg['name']} + {len(list(SEED_DIR.rglob('*.md')))} fichiers de départ",
        f"agent          {'mise à jour' if state.get('agent_id') else 'création'} : {agent_cfg['name']} "
        f"({len(agent_cfg.get('tools', []))} outils, {len(agent_cfg.get('skills', []))} skills Anthropic)",
    ]
    for p in sorted(DEPLOY_DIR.glob("*.md")):
        cfg, _ = read_front_matter(p)
        known = p.stem in state.get("deployments", {})
        lines.append(f"tâche planifiée {'mise à jour' if known else 'création'} : {cfg['name']} ({cfg['schedule']['expression']})")
    return lines


def sync(
    client,
    state_path: Path,
    *,
    repo_url: str = "",
    repo_token: str = "",
    branch: str = "main",
    deployment_budget_cents: int = 200,
    skip_deployments: bool = False,
    log: Callable[[str], None] = print,
) -> dict:
    """Applique les fichiers du dépôt chez Anthropic. Sans effet de bord si rien n'a changé."""
    import anthropic

    state = load_state(state_path)
    agent_cfg, system_prompt = read_front_matter(AGENT_FILE)
    env_cfg = yaml.safe_load(ENV_FILE.read_text(encoding="utf-8"))
    mem_cfg = yaml.safe_load(MEMORY_FILE.read_text(encoding="utf-8"))

    # 1. Environnement
    if state.get("environment_id"):
        client.beta.environments.update(
            state["environment_id"], name=env_cfg["name"], config=env_cfg["config"], description=env_cfg.get("description")
        )
        log(f"Environnement à jour : {state['environment_id']}")
    else:
        env = client.beta.environments.create(name=env_cfg["name"], config=env_cfg["config"], description=env_cfg.get("description"))
        state["environment_id"] = env.id
        save_state(state_path, state)
        log(f"Environnement créé : {env.id}")

    # 2. Mémoire durable (on ne remplace jamais ce que l'agent a appris)
    if not state.get("memory_store_id"):
        store = client.beta.memory_stores.create(name=mem_cfg["name"], description=mem_cfg["description"])
        state["memory_store_id"] = store.id
        save_state(state_path, state)
        log(f"Mémoire créée : {store.id}")
    if not state.get("memory_seeded"):
        for f in sorted(SEED_DIR.rglob("*.md")):
            path = "/" + f.relative_to(SEED_DIR).as_posix()
            try:
                client.beta.memory_stores.memories.create(state["memory_store_id"], path=path, content=f.read_text(encoding="utf-8"))
                log(f"  mémoire : {path} ajouté")
            except anthropic.ConflictError:
                pass
        state["memory_seeded"] = True
        save_state(state_path, state)

    # 3. Agent (une modification crée une nouvelle version ; sinon rien ne change)
    fields = {k: agent_cfg[k] for k in ("name", "description", "model", "tools", "skills", "mcp_servers") if k in agent_cfg}
    fields["system"] = system_prompt
    if state.get("agent_id"):
        agent = client.beta.agents.update(state["agent_id"], **fields)
    else:
        agent = client.beta.agents.create(**fields)
    state["agent_id"], state["agent_version"] = agent.id, agent.version
    save_state(state_path, state)
    log(f"Agent : {agent.id} (version {agent.version})")

    # 4. Tâches planifiées
    if not skip_deployments:
        resources = session_resources(state["memory_store_id"], repo_url, repo_token, branch)
        if len(resources) == 1:
            log("  ! Pas de GITHUB_TOKEN : les tâches planifiées n'auront pas les skills du dépôt.")
        state.setdefault("deployments", {})
        for p in sorted(DEPLOY_DIR.glob("*.md")):
            cfg, body = read_front_matter(p)
            payload = {
                "name": cfg["name"],
                "agent": agent.id,
                "environment_id": state["environment_id"],
                "initial_events": [{"type": "user.message", "content": [{"type": "text", "text": body}]}],
                "schedule": cfg["schedule"],
                "resources": resources,
            }
            if deployment_budget_cents > 0:
                payload["budget"] = {"type": "limit", "max_list_cost": {"amount": str(deployment_budget_cents), "currency": "USD"}}
            dep_id = state["deployments"].get(p.stem)
            if dep_id:
                client.beta.deployments.update(dep_id, **payload)
                log(f"Tâche planifiée à jour : {cfg['name']}")
            else:
                dep = client.beta.deployments.create(**payload)
                state["deployments"][p.stem] = dep.id
                save_state(state_path, state)
                log(f"Tâche planifiée créée : {cfg['name']} ({dep.id})")
    return state


def ids_for_settings(state: dict) -> dict[str, Optional[str]]:
    return {k: state.get(k) for k in ("agent_id", "environment_id", "memory_store_id")}
