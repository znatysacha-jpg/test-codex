"""Connecteur claude.ai (serveur MCP) : c'est par lui que l'app iPhone parle à l'agent.

À ajouter une fois dans claude.ai > Réglages > Connecteurs > Ajouter un connecteur personnalisé,
avec l'URL https://<votre-passerelle>/mcp/<MCP_SECRET>/ et le nom « Instinct perso ».
Le secret dans l'URL est la clé : quiconque la connaît peut parler à votre agent. Ne la partagez pas.
"""

from __future__ import annotations

import base64
from typing import Any, Optional

from mcp.server.mcpserver import MCPServer

from .bridge import Bridge

MAX_FILE_BYTES = 8 * 1024 * 1024


def build_connector(bridge: Bridge) -> MCPServer:
    srv = MCPServer(
        name="Instinct perso",
        instructions=(
            "Passerelle vers l'agent personnel de l'utilisateur. `envoyer` lui transmet une demande, `messages` lit ses réponses "
            "(texte, validations à boutons, messages WhatsApp prêts, options de réservation, fichiers), `repondre` répond à une validation."
        ),
    )
    store = bridge.store

    @srv.tool(description="Envoie un message de l'utilisateur à son agent. La réponse arrive ensuite dans `messages`.")
    def envoyer(texte: str) -> dict:
        texte = texte.strip()
        if not texte:
            return {"ok": False, "erreur": "message vide"}
        bridge.spawn(bridge.handle_user_input, "app", [{"type": "text", "text": texte}], texte)
        return {"ok": True, "dernier_id": store.last_message_id()}

    @srv.tool(
        description=(
            "Lit l'historique de la conversation. `apres` = id du dernier message déjà affiché (0 = les plus récents). "
            "Chaque message a id, role (agent|user), kind (text|choices|whatsapp|options|file), text, data, at."
        )
    )
    def messages(apres: int = 0, limite: int = 50) -> dict:
        limite = max(1, min(int(limite), 200))
        items = store.messages_after(int(apres), limite)
        open_ids = {p["id"] for p in store.open_pending()}
        for m in items:
            if m["kind"] == "choices":
                m["data"]["ouverte"] = m["data"].get("validation_id") in open_ids
        return {"messages": items, "en_attente": len(open_ids)}

    @srv.tool(description="Répond à une validation : `choix` = index du bouton (0 = première option). Ou `texte` pour répondre librement.")
    def repondre(validation_id: str, choix: Optional[int] = None, texte: str = "") -> dict:
        note = bridge.resolve(validation_id, choix, free_text=texte)
        store.add_message("user", "text", texte or f"→ {note}", channel="app")
        return {"ok": True, "note": note}

    @srv.tool(description="Démarre une nouvelle conversation avec l'agent (sa mémoire durable est conservée).")
    def nouvelle_conversation() -> dict:
        bridge.reset()
        store.add_message("agent", "text", "Nouvelle conversation. Je garde ma mémoire.", channel="app")
        return {"ok": True}

    @srv.tool(description="Arrête ce que l'agent est en train de faire.")
    def arreter() -> dict:
        bridge.interrupt()
        return {"ok": True}

    @srv.tool(description="Liste les fichiers de la mémoire de l'agent sous un dossier (ex. '/crm/').")
    def memoire_liste(prefixe: str = "/") -> dict:
        if not bridge.s.memory_store_id:
            return {"fichiers": []}
        out = []
        for m in bridge.client.beta.memory_stores.memories.list(bridge.s.memory_store_id, path_prefix=prefixe or "/"):
            if getattr(m, "type", "") == "memory":
                out.append({"chemin": m.path, "taille": getattr(m, "content_size_bytes", 0)})
        return {"fichiers": sorted(out, key=lambda x: x["chemin"])}

    @srv.tool(description="Lit un fichier de la mémoire de l'agent (ex. '/crm/pipeline.md').")
    def memoire_lire(chemin: str) -> dict:
        if not bridge.s.memory_store_id:
            return {"contenu": ""}
        for m in bridge.client.beta.memory_stores.memories.list(bridge.s.memory_store_id, path_prefix=chemin, view="full"):
            if getattr(m, "type", "") == "memory" and m.path == chemin:
                return {"chemin": chemin, "contenu": m.content}
        return {"chemin": chemin, "contenu": "", "erreur": "introuvable"}

    @srv.tool(description="Télécharge un fichier produit par l'agent (contenu en base64).")
    def fichier(file_id: str) -> dict:
        found = store.get_file(file_id)
        if not found:
            return {"erreur": "introuvable"}
        name, data = found
        if len(data) > MAX_FILE_BYTES:
            return {"erreur": "fichier trop gros pour l'app, il est aussi dans Telegram"}
        return {"nom": name, "base64": base64.b64encode(data).decode()}

    @srv.tool(description="État de l'agent : services connectés et validations en attente.")
    def statut() -> dict[str, Any]:
        s = bridge.s
        return {
            "agent": bool(s.agent_id),
            "google": s.google_enabled,
            "telegram": s.telegram_enabled,
            "whatsapp": s.whatsapp_enabled,
            "skills": bool(s.github_repo_url and s.github_token),
            "en_attente": len(store.open_pending()),
        }

    return srv
