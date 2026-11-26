"""Outils maison de l'agent : exécution et textes de validation.

Les outils de NEEDS_APPROVAL ne s'exécutent qu'après un « oui » explicite de l'utilisateur.
Cette règle est appliquée ici, dans le code, et pas seulement dans le prompt de l'agent.
"""

from __future__ import annotations

import json
from typing import Any

from .google_tools import Google, GoogleNotConfigured

NEEDS_APPROVAL = {"gmail_send", "calendar_create", "demander_validation"}
# Outils qui affichent quelque chose à l'utilisateur (carte) au lieu d'appeler un service.
PRESENTATION = {"preparer_whatsapp", "proposer_options"}
DEFAULT_APPROVAL_OPTIONS = ["✅ Valider", "❌ Refuser"]


def presentation_card(name: str, data: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Renvoie (type de carte, contenu de la carte, résultat pour l'agent)."""
    from .channels import whatsapp_link

    if name == "preparer_whatsapp":
        numero = str(data.get("numero", "")).strip()
        message = str(data.get("message", "")).strip()
        if not numero or not message:
            raise ToolError("Il faut un numéro et un message.")
        card = {"nom": data.get("nom", ""), "numero": numero, "message": message, "lien": whatsapp_link(numero, message)}
        return "whatsapp", card, {"statut": "message proposé à l'utilisateur : il l'ouvre dans WhatsApp et l'envoie lui-même."}
    if name == "proposer_options":
        options = []
        for opt in (data.get("options") or [])[:6]:
            lien = str(opt.get("lien", ""))
            options.append(
                {
                    "titre": str(opt.get("titre", ""))[:120],
                    "details": str(opt.get("details", ""))[:400],
                    "prix": str(opt.get("prix", ""))[:40],
                    "lien": lien if lien.startswith("https://") else "",
                }
            )
        if not options:
            raise ToolError("Aucune option à présenter.")
        card = {"titre": str(data.get("titre", "Options"))[:200], "options": options}
        return "options", card, {"statut": f"{len(options)} options présentées à l'utilisateur."}
    raise ToolError(f"Outil inconnu : {name}")


class ToolError(Exception):
    pass


def approval_prompt(name: str, data: dict[str, Any]) -> tuple[str, list[str]]:
    """Texte montré à l'utilisateur avant une action, et boutons proposés."""
    if name == "gmail_send":
        lines = ["📧 J'envoie cet e-mail ?", "", f"À : {data.get('to', '')}"]
        if data.get("cc"):
            lines.append(f"Cc : {data['cc']}")
        lines += [f"Objet : {data.get('subject', '')}", "", data.get("body", "")]
        return "\n".join(lines), DEFAULT_APPROVAL_OPTIONS
    if name == "calendar_create":
        lines = [
            "📅 Je crée ce rendez-vous ?",
            "",
            data.get("summary", ""),
            f"Début : {data.get('start', '')}",
            f"Fin : {data.get('end', '')}",
        ]
        if data.get("location"):
            lines.append(f"Lieu : {data['location']}")
        if data.get("attendees"):
            lines.append("Invitations envoyées à : " + ", ".join(data["attendees"]))
        return "\n".join(lines), DEFAULT_APPROVAL_OPTIONS
    if name == "demander_validation":
        options = [str(o).strip()[:20] for o in (data.get("options") or []) if str(o).strip()][:4]
        if len(options) < 2:
            options = DEFAULT_APPROVAL_OPTIONS
        return "❓ " + str(data.get("question", "")).strip(), options
    return f"Valider l'action {name} ?", DEFAULT_APPROVAL_OPTIONS


def confirmation_prompt(tool_name: str, tool_input: dict[str, Any]) -> tuple[str, list[str]]:
    """Pour un outil intégré (bash, web…) que la plateforme a mis en pause faute de pouvoir trancher."""
    detail = tool_input.get("command") or tool_input.get("url") or tool_input.get("file_path") or json.dumps(tool_input, ensure_ascii=False)
    return (f"⚠️ L'agent veut utiliser « {tool_name} » :\n\n{str(detail)[:1500]}\n\nJe le laisse faire ?", ["✅ Autoriser", "❌ Bloquer"])


def execute(name: str, data: dict[str, Any], google: Google) -> dict[str, Any] | list[Any]:
    """Exécute un outil maison et renvoie un résultat sérialisable en JSON."""
    try:
        if name == "gmail_search":
            return google.gmail_search(data["query"], data.get("max_results", 10))
        if name == "gmail_read":
            return google.gmail_read(data["message_id"])
        if name == "gmail_draft":
            return google.gmail_draft(data["to"], data["subject"], data["body"], data.get("cc", ""), data.get("thread_id", ""))
        if name == "gmail_send":
            return google.gmail_send(data["to"], data["subject"], data["body"], data.get("cc", ""), data.get("thread_id", ""))
        if name == "contacts_search":
            return google.contacts_search(data["query"])
        if name == "calendar_list":
            return google.calendar_list(data["time_min"], data["time_max"], data.get("max_results", 50))
        if name == "calendar_create":
            return google.calendar_create(
                data["summary"], data["start"], data["end"], data.get("attendees"), data.get("location", ""), data.get("description", "")
            )
    except GoogleNotConfigured as e:
        raise ToolError(str(e)) from e
    except KeyError as e:
        raise ToolError(f"Paramètre manquant : {e}") from e
    except Exception as e:  # erreurs de l'API Google : on les rend à l'agent plutôt que de planter
        raise ToolError(f"{type(e).__name__} : {e}") from e
    raise ToolError(f"Outil inconnu : {name}")


def result_after_decision(name: str, data: dict[str, Any], options: list[str], choice: int | None, free_text: str, google: Google):
    """Résultat renvoyé à l'agent une fois que l'utilisateur a répondu à une validation."""
    if choice is None:
        return {
            "statut": "pas de choix",
            "message_de_l_utilisateur": free_text,
            "consigne": "L'utilisateur a répondu par un message au lieu de choisir. Rien n'a été fait. Tiens compte de sa réponse.",
        }
    chosen = options[choice] if 0 <= choice < len(options) else ""
    if name == "demander_validation":
        return {"choix": chosen, "index": choice}
    if choice == 0:
        return execute(name, data, google)
    return {"statut": "refusé par l'utilisateur", "consigne": "Rien n'a été fait. Ne réessaie pas sans nouvelle demande de sa part."}


YES_WORDS = {"oui", "ok", "okay", "yes", "go", "vas-y", "vas y", "valide", "valider", "d'accord", "dac", "ouais", "parfait", "c'est bon", "envoie", "confirme"}
NO_WORDS = {"non", "no", "stop", "annule", "annuler", "refuse", "refuser", "pas maintenant", "laisse tomber"}


def parse_reply(text: str, n_options: int) -> int | None:
    """Traduit une réponse écrite (« oui », « non », « 2 ») en index d'option."""
    t = text.strip().lower().rstrip(" !.")
    if t.isdigit() and 1 <= int(t) <= n_options:
        return int(t) - 1
    if t in YES_WORDS or t.startswith("oui"):
        return 0
    if t in NO_WORDS or t.startswith("non"):
        return n_options - 1 if n_options >= 2 else None
    return None
