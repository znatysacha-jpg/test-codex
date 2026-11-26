"""Canaux de messagerie : Telegram (Bot API) et WhatsApp (Cloud API de Meta).

Les deux exposent la même interface : send_text, send_choices, send_file, typing.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from typing import Optional
from urllib.parse import quote

import httpx

from .config import Settings

log = logging.getLogger("instinct.channels")

TELEGRAM_LIMIT = 4000
WHATSAPP_LIMIT = 4000


def split_text(text: str, limit: int) -> list[str]:
    """Découpe un long message sur les sauts de ligne pour respecter la limite du canal."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    parts, current = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:limit])
            line = line[limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            parts.append(current)
            current = line
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


class Channel:
    name = "base"

    def send_text(self, text: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def send_choices(self, text: str, options: list[str], pending_id: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def send_file(self, filename: str, data: bytes, caption: str = "") -> None:  # pragma: no cover
        raise NotImplementedError

    def send_card(self, kind: str, data: dict) -> None:
        """Carte riche (message WhatsApp prêt, options de réservation). Par défaut : rendu en texte avec liens."""
        self.send_text(card_as_text(kind, data))

    def typing(self) -> None:
        pass


def whatsapp_link(number: str, message: str) -> str:
    digits = "".join(c for c in number if c.isdigit())
    if digits.startswith("0") and len(digits) == 10:  # numéro français 06… -> 336…
        digits = "33" + digits[1:]
    return f"https://wa.me/{digits}?text={quote(message)}"


def card_as_text(kind: str, data: dict) -> str:
    if kind == "whatsapp":
        return (
            f"💬 Message WhatsApp prêt pour {data.get('nom', '')} :\n\n{data.get('message', '')}\n\n"
            f"Touche le lien pour l'ouvrir dans WhatsApp, puis envoie :\n{data.get('lien', '')}"
        )
    if kind == "options":
        lines = [str(data.get("titre", ""))]
        for i, opt in enumerate(data.get("options", []), 1):
            lines.append("")
            lines.append(f"{i}. {opt.get('titre', '')}" + (f" · {opt['prix']}" if opt.get("prix") else ""))
            if opt.get("details"):
                lines.append(str(opt["details"]))
            if opt.get("lien"):
                lines.append(str(opt["lien"]))
        return "\n".join(lines).strip()
    return json.dumps(data, ensure_ascii=False)


class AppChannel(Channel):
    """L'app iPhone (artefact claude.ai) : les messages sont gardés ici et lus par l'app via le connecteur."""

    name = "app"

    def __init__(self, store):
        self.store = store

    def send_text(self, text: str) -> None:
        if text.strip():
            self.store.add_message("agent", "text", text.strip(), channel=self.name)

    def send_choices(self, text: str, options: list[str], pending_id: str) -> None:
        self.store.add_message("agent", "choices", text, {"options": options, "validation_id": pending_id}, channel=self.name)

    def send_file(self, filename: str, data: bytes, caption: str = "") -> None:
        file_id = uuid.uuid4().hex[:12]
        self.store.put_file(file_id, filename, data)
        self.store.add_message("agent", "file", caption, {"file_id": file_id, "filename": filename, "taille": len(data)}, channel=self.name)

    def send_card(self, kind: str, data: dict) -> None:
        self.store.add_message("agent", kind, "", data, channel=self.name)


class Telegram(Channel):
    name = "telegram"

    def __init__(self, settings: Settings, http: Optional[httpx.Client] = None):
        self.s = settings
        self.chat_id = settings.owner_telegram_id
        self.http = http or httpx.Client(timeout=30)
        self.base = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

    def _call(self, method: str, **kwargs) -> dict:
        r = self.http.post(f"{self.base}/{method}", **kwargs)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not data.get("ok"):
            log.warning("Telegram %s a échoué : %s", method, r.text[:300])
        return data

    def send_text(self, text: str) -> None:
        for part in split_text(text, TELEGRAM_LIMIT):
            self._call("sendMessage", json={"chat_id": self.chat_id, "text": part, "disable_web_page_preview": True})

    def send_choices(self, text: str, options: list[str], pending_id: str) -> None:
        keyboard = [[{"text": opt[:40], "callback_data": f"ap:{pending_id}:{i}"}] for i, opt in enumerate(options)]
        body = split_text(text, TELEGRAM_LIMIT)
        for part in body[:-1]:
            self._call("sendMessage", json={"chat_id": self.chat_id, "text": part})
        self._call(
            "sendMessage",
            json={"chat_id": self.chat_id, "text": body[-1] if body else "?", "reply_markup": {"inline_keyboard": keyboard}},
        )

    def send_file(self, filename: str, data: bytes, caption: str = "") -> None:
        self._call(
            "sendDocument",
            data={"chat_id": self.chat_id, "caption": caption[:1000]},
            files={"document": (filename, data)},
        )

    def typing(self) -> None:
        self._call("sendChatAction", json={"chat_id": self.chat_id, "action": "typing"})

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        self._call("answerCallbackQuery", json={"callback_query_id": callback_id, "text": text[:180]})

    def remove_buttons(self, chat_id: int | str, message_id: int, note: str) -> None:
        self._call("editMessageReplyMarkup", json={"chat_id": chat_id, "message_id": message_id, "reply_markup": {"inline_keyboard": []}})
        if note:
            self._call("sendMessage", json={"chat_id": chat_id, "text": note})

    def download(self, file_id: str) -> tuple[bytes, str]:
        info = self._call("getFile", json={"file_id": file_id}).get("result", {})
        path = info.get("file_path", "")
        r = self.http.get(f"https://api.telegram.org/file/bot{self.s.telegram_bot_token}/{path}")
        r.raise_for_status()
        return r.content, path

    def set_webhook(self, url: str) -> dict:
        return self._call(
            "setWebhook",
            json={
                "url": url,
                "secret_token": self.s.telegram_webhook_secret,
                "allowed_updates": ["message", "callback_query"],
                "drop_pending_updates": False,
            },
        )


class WhatsApp(Channel):
    """WhatsApp Cloud API.

    Attention : depuis le 15 janvier 2026, les conditions de l'API WhatsApp Business interdisent
    les assistants IA généralistes, et un message envoyé plus de 24 h après le dernier message de
    l'utilisateur exige un modèle (template) validé par Meta. Les tâches planifiées passent donc
    par Telegram par défaut.
    """

    name = "whatsapp"

    def __init__(self, settings: Settings, http: Optional[httpx.Client] = None):
        self.s = settings
        self.to = settings.owner_whatsapp_number
        self.http = http or httpx.Client(timeout=30)
        self.base = f"https://graph.facebook.com/{settings.whatsapp_api_version}"
        self.headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}

    def _send(self, payload: dict) -> dict:
        payload = {"messaging_product": "whatsapp", "to": self.to, **payload}
        r = self.http.post(f"{self.base}/{self.s.whatsapp_phone_number_id}/messages", json=payload, headers=self.headers)
        if r.status_code >= 300:
            log.warning("WhatsApp a refusé le message : %s", r.text[:300])
        return r.json() if r.content else {}

    def send_text(self, text: str) -> None:
        for part in split_text(text, WHATSAPP_LIMIT):
            self._send({"type": "text", "text": {"body": part, "preview_url": False}})

    def send_choices(self, text: str, options: list[str], pending_id: str) -> None:
        body = split_text(text, 1000)
        for part in body[:-1]:
            self.send_text(part)
        if len(options) <= 3:
            buttons = [{"type": "reply", "reply": {"id": f"ap:{pending_id}:{i}", "title": opt[:20]}} for i, opt in enumerate(options)]
            self._send({"type": "interactive", "interactive": {"type": "button", "body": {"text": body[-1] if body else "?"}, "action": {"buttons": buttons}}})
        else:
            lines = "\n".join(f"{i + 1}. {opt}" for i, opt in enumerate(options))
            self.send_text(f"{body[-1] if body else ''}\n\n{lines}\n\nRéponds par le numéro de ton choix.")

    def send_file(self, filename: str, data: bytes, caption: str = "") -> None:
        r = self.http.post(
            f"{self.base}/{self.s.whatsapp_phone_number_id}/media",
            headers=self.headers,
            data={"messaging_product": "whatsapp"},
            files={"file": (filename, data, "application/octet-stream")},
        )
        media_id = r.json().get("id") if r.content else None
        if not media_id:
            log.warning("Envoi du fichier WhatsApp impossible : %s", r.text[:300])
            return
        self._send({"type": "document", "document": {"id": media_id, "filename": filename, "caption": caption[:1000]}})

    def download(self, media_id: str) -> tuple[bytes, str]:
        meta = self.http.get(f"{self.base}/{media_id}", headers=self.headers).json()
        r = self.http.get(meta["url"], headers=self.headers)
        r.raise_for_status()
        return r.content, meta.get("mime_type", "")

    def verify_signature(self, raw_body: bytes, header: str) -> bool:
        if not self.s.whatsapp_app_secret:
            return False
        expected = "sha256=" + hmac.new(self.s.whatsapp_app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, header or "")
