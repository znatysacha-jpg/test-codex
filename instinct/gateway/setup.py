"""Mise en route automatique : création de l'agent, webhook Telegram, connexion Google par lien, message de réglages."""

from __future__ import annotations

import logging
import secrets
import time
from pathlib import Path
from typing import Optional

from .config import STATE_FILE, Settings
from .store import Store

log = logging.getLogger("instinct.setup")
LINK_TTL = 30 * 60


def bootstrap(bridge, client, s: Settings) -> None:
    """Crée ou met à jour l'agent chez Anthropic, puis branche Telegram. Lancé au démarrage."""
    if s.auto_provision:
        try:
            from .provisioning import sync

            state = sync(
                client,
                Path(STATE_FILE),
                repo_url=s.github_repo_url,
                repo_token=s.github_token,
                branch=s.github_branch,
                deployment_budget_cents=s.deployment_budget_cents,
                log=log.info,
            )
            s.agent_id = state["agent_id"]
            s.environment_id = state["environment_id"]
            s.memory_store_id = state["memory_store_id"]
        except Exception:
            log.exception("Création automatique de l'agent impossible (vérifiez ANTHROPIC_API_KEY)")
    if s.telegram_enabled and s.public_base_url and "telegram" in bridge.channels:
        result = bridge.channels["telegram"].set_webhook(f"{s.public_base_url}/telegram/webhook")
        log.info("Webhook Telegram : %s", "OK" if result.get("ok") else result)


# ------------------------------------------------------------------ Google
def google_ready_for_link(s: Settings) -> bool:
    return bool(s.public_base_url and s.google_client_id and s.google_client_secret)


def google_link(store: Store, s: Settings) -> Optional[str]:
    """Lien à usage unique (30 min) pour connecter Gmail, Agenda et Contacts depuis le téléphone."""
    if not google_ready_for_link(s):
        return None
    token = secrets.token_urlsafe(24)
    store.set("google_link_token", f"{token}:{int(time.time())}")
    return f"{s.public_base_url}/google/connect?t={token}"


def check_link_token(store: Store, token: str) -> bool:
    raw = store.get("google_link_token") or ""
    saved, _, at = raw.partition(":")
    ok = bool(saved) and secrets.compare_digest(saved, token or "") and time.time() - int(at or 0) < LINK_TTL
    if ok:
        store.delete("google_link_token")  # usage unique
    return ok


def google_flow(s: Settings, state: Optional[str] = None):
    from google_auth_oauthlib.flow import Flow

    from .google_tools import SCOPES

    redirect = f"{s.public_base_url}/google/callback"
    config = {
        "web": {
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect],
        }
    }
    return Flow.from_client_config(config, scopes=SCOPES, state=state, redirect_uri=redirect)


# ------------------------------------------------------------------ message de réglages
def setup_message(store: Store, s: Settings) -> str:
    """Ce que l'utilisateur doit coller ailleurs : envoyé uniquement au propriétaire, sur Telegram."""
    if not s.public_base_url:
        return "Adresse publique inconnue : définis PUBLIC_BASE_URL sur la passerelle pour obtenir les réglages."
    lines = ["Réglages de ton agent", ""]
    lines.append("1. App iPhone : dans claude.ai › Réglages › Connecteurs › Ajouter un connecteur personnalisé")
    if s.mcp_secret:
        lines += ["Nom : Instinct perso", "Adresse :", f"{s.public_base_url}/mcp/{s.mcp_secret}/"]
    else:
        lines.append("(MCP_SECRET n'est pas défini sur la passerelle)")
    lines += ["", "2. Siri (app Raccourcis, action « Obtenir le contenu de l'URL ») :"]
    if s.siri_token:
        lines += [f"{s.public_base_url}/siri", "Méthode POST, en-tête Authorization :", f"Bearer {s.siri_token}", "Corps JSON : texte = Texte dicté"]
    else:
        lines.append("(SIRI_TOKEN n'est pas défini sur la passerelle)")
    lines += ["", "3. Google (Gmail, Agenda, Contacts) :"]
    if s.google_enabled:
        lines.append("Déjà connecté.")
    else:
        link = google_link(store, s)
        lines.append(f"Ouvre ce lien (valable 30 min) :\n{link}" if link else "Renseigne GOOGLE_CLIENT_ID et GOOGLE_CLIENT_SECRET sur la passerelle.")
    lines += [
        "",
        "4. Webhook Anthropic (facultatif, accélère les tâches planifiées) : console Anthropic › Manage › Webhooks",
        f"{s.public_base_url}/anthropic/webhook",
        "",
        "Garde ce message pour toi : il contient des clés d'accès.",
    ]
    return "\n".join(lines)
