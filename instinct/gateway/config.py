"""Configuration de la passerelle, lue depuis les variables d'environnement."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = Path(os.environ.get("STATE_PATH") or ROOT / "state.json")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _state() -> dict:
    """IDs écrits par scripts/provision.py (agent, environnement, mémoire)."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


@dataclass
class Settings:
    # Anthropic (ANTHROPIC_API_KEY est lu directement par le SDK)
    agent_id: str = ""
    environment_id: str = ""
    memory_store_id: str = ""
    workspace: str = "default"
    session_budget_cents: int = 0  # 0 = pas de plafond par session

    # Dépôt GitHub monté dans chaque session (il apporte les skills de .claude/skills)
    github_repo_url: str = ""
    github_branch: str = "main"
    github_token: str = ""

    # Canaux
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    owner_telegram_id: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v21.0"
    owner_whatsapp_number: str = ""
    default_channel: str = "telegram"

    # Google (Gmail + Agenda)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""

    # App iPhone (connecteur claude.ai) et Siri
    mcp_secret: str = ""
    siri_token: str = ""

    # Mise en route automatique
    public_base_url: str = ""          # adresse publique de la passerelle (Render la fournit seul)
    auto_provision: bool = True        # crée / met à jour l'agent chez Anthropic au démarrage
    deployment_budget_cents: int = 200

    # Divers
    db_path: str = str(ROOT / "data" / "instinct.db")
    poll_seconds: int = 90
    timezone: str = "Europe/Paris"
    extra: dict = field(default_factory=dict)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.owner_telegram_id)

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.whatsapp_token and self.whatsapp_phone_number_id and self.owner_whatsapp_number)

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.google_refresh_token)


def load_settings() -> Settings:
    st = _state()
    return Settings(
        agent_id=_env("AGENT_ID", st.get("agent_id", "")),
        environment_id=_env("ENVIRONMENT_ID", st.get("environment_id", "")),
        memory_store_id=_env("MEMORY_STORE_ID", st.get("memory_store_id", "")),
        workspace=_env("ANTHROPIC_WORKSPACE", "default"),
        session_budget_cents=int(_env("SESSION_BUDGET_CENTS", "0") or 0),
        github_repo_url=_env("GITHUB_REPO_URL"),
        github_branch=_env("GITHUB_BRANCH", "main"),
        github_token=_env("GITHUB_TOKEN"),
        telegram_bot_token=_env("TELEGRAM_BOT_TOKEN"),
        telegram_webhook_secret=_env("TELEGRAM_WEBHOOK_SECRET"),
        owner_telegram_id=_env("OWNER_TELEGRAM_ID"),
        whatsapp_token=_env("WHATSAPP_TOKEN"),
        whatsapp_phone_number_id=_env("WHATSAPP_PHONE_NUMBER_ID"),
        whatsapp_verify_token=_env("WHATSAPP_VERIFY_TOKEN"),
        whatsapp_app_secret=_env("WHATSAPP_APP_SECRET"),
        whatsapp_api_version=_env("WHATSAPP_API_VERSION", "v21.0"),
        owner_whatsapp_number=_env("OWNER_WHATSAPP_NUMBER").lstrip("+"),
        default_channel=_env("DEFAULT_CHANNEL", "telegram"),
        google_client_id=_env("GOOGLE_CLIENT_ID"),
        google_client_secret=_env("GOOGLE_CLIENT_SECRET"),
        google_refresh_token=_env("GOOGLE_REFRESH_TOKEN"),
        mcp_secret=_env("MCP_SECRET"),
        siri_token=_env("SIRI_TOKEN"),
        public_base_url=(_env("PUBLIC_BASE_URL") or _env("RENDER_EXTERNAL_URL")).rstrip("/"),
        auto_provision=_env("AUTO_PROVISION", "1") not in ("0", "false", "non"),
        deployment_budget_cents=int(_env("DEPLOYMENT_BUDGET_CENTS", "200") or 0),
        db_path=_env("DB_PATH", str(ROOT / "data" / "instinct.db")),
        poll_seconds=int(_env("POLL_SECONDS", "90") or 90),
        timezone=_env("TIMEZONE", "Europe/Paris"),
    )
