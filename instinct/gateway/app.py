"""Serveur web de la passerelle : webhooks Telegram, WhatsApp et Anthropic.

Lancement local : uvicorn gateway.app:app --port 8000
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import threading
from contextlib import asynccontextmanager
from typing import Any, Optional

import anthropic
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .bridge import Bridge
from .channels import Channel, Telegram, WhatsApp
from .config import Settings, load_settings
from .google_tools import Google
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
log = logging.getLogger("instinct.app")

HELP = (
    "Je suis ton agent personnel. Écris-moi comme à un assistant : e-mails, agenda, prospects, projets, équipe, recherches, réservations.\n\n"
    "/new  nouvelle conversation (ma mémoire est conservée)\n"
    "/stop  j'arrête ce que je suis en train de faire\n"
    "/aide  ce message"
)
VOICE_REPLY = "Je ne sais pas encore écouter les messages vocaux. Envoie-moi un texte (la dictée du clavier marche très bien)."


def _run_async(fn, *args) -> None:
    threading.Thread(target=fn, args=args, daemon=True).start()


def build(settings: Optional[Settings] = None, client: Optional[anthropic.Anthropic] = None) -> tuple[FastAPI, Bridge]:
    s = settings or load_settings()
    client = client or anthropic.Anthropic()
    channels: dict[str, Channel] = {}
    if s.telegram_enabled:
        channels["telegram"] = Telegram(s)
    if s.whatsapp_enabled:
        channels["whatsapp"] = WhatsApp(s)
    bridge = Bridge(client, Store(s.db_path), s, channels, Google(s))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Sondage de secours : rattrape les sessions en pause si un webhook ou un flux a été manqué.
        if s.agent_id and s.poll_seconds > 0:
            threading.Thread(target=bridge.poll_forever, daemon=True).start()
        yield

    app = FastAPI(title="Instinct perso", docs_url=None, redoc_url=None, lifespan=lifespan)

    @app.get("/health")
    def health() -> dict:
        return {
            "ok": bool(s.agent_id and s.environment_id),
            "telegram": s.telegram_enabled,
            "whatsapp": s.whatsapp_enabled,
            "google": s.google_enabled,
            "skills_repo": bool(s.github_repo_url and s.github_token),
        }

    # ------------------------------------------------------------- commandes
    def command(channel: str, text: str) -> bool:
        cmd = text.strip().split()[0].lower() if text.strip() else ""
        ch = channels[channel]
        if cmd in ("/start", "/aide", "/help"):
            ch.send_text(HELP)
        elif cmd == "/new":
            bridge.reset()
            ch.send_text("C'est noté, on repart sur une nouvelle conversation. Je garde ma mémoire.")
        elif cmd == "/stop":
            bridge.interrupt()
            ch.send_text("J'arrête.")
        else:
            return False
        return True

    def text_input(channel: str, text: str) -> None:
        if text.startswith("/") and command(channel, text):
            return
        channels[channel].typing()
        bridge.handle_user_input(channel, [{"type": "text", "text": text}], text_for_approval=text)

    def file_input(channel: str, data: bytes, filename: str, mime: str, caption: str) -> None:
        mime = mime or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        intro = caption or "Voici un fichier."
        if mime.startswith("image/"):
            block = {"type": "image", "source": {"type": "base64", "media_type": mime, "data": base64.b64encode(data).decode()}}
            content = [block, {"type": "text", "text": intro}]
        elif mime == "application/pdf":
            block = {"type": "document", "title": filename, "source": {"type": "base64", "media_type": mime, "data": base64.b64encode(data).decode()}}
            content = [block, {"type": "text", "text": intro}]
        elif mime.startswith("text/") or filename.endswith((".csv", ".md", ".json", ".txt")):
            block = {"type": "document", "title": filename, "source": {"type": "text", "media_type": "text/plain", "data": data.decode("utf-8", "replace")}}
            content = [block, {"type": "text", "text": intro}]
        else:
            # Excel, Word… : on dépose le fichier dans le conteneur de la session.
            uploaded = client.files.upload(file=(filename, data, mime))
            sid = bridge.main_session()
            client.beta.sessions.resources.add(sid, file_id=uploaded.id, type="file", mount_path=f"/{filename}")
            content = [{"type": "text", "text": f"{intro}\n(Fichier déposé dans /mnt/session/uploads/{filename})"}]
        bridge.handle_user_input(channel, content)

    # ------------------------------------------------------------- Telegram
    @app.post("/telegram/webhook")
    async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(default="")) -> dict:
        if "telegram" not in channels or x_telegram_bot_api_secret_token != s.telegram_webhook_secret:
            raise HTTPException(status_code=403)
        update: dict[str, Any] = await request.json()
        tg: Telegram = channels["telegram"]  # type: ignore[assignment]

        cb = update.get("callback_query")
        if cb:
            if str(cb.get("from", {}).get("id")) != s.owner_telegram_id:
                return {"ok": True}
            _run_async(_telegram_callback, tg, cb)
            return {"ok": True}

        msg = update.get("message") or {}
        if str(msg.get("from", {}).get("id")) != s.owner_telegram_id:
            log.warning("Message Telegram ignoré (expéditeur inconnu %s)", msg.get("from", {}).get("id"))
            return {"ok": True}
        if "text" in msg:
            _run_async(text_input, "telegram", msg["text"])
        elif "photo" in msg:
            _run_async(_telegram_file, tg, msg["photo"][-1]["file_id"], "photo.jpg", "image/jpeg", msg.get("caption", ""))
        elif "document" in msg:
            doc = msg["document"]
            _run_async(_telegram_file, tg, doc["file_id"], doc.get("file_name", "document"), doc.get("mime_type", ""), msg.get("caption", ""))
        elif "voice" in msg or "audio" in msg:
            tg.send_text(VOICE_REPLY)
        return {"ok": True}

    def _telegram_callback(tg: Telegram, cb: dict) -> None:
        try:
            _, pid, idx = cb.get("data", "").split(":")
            note = bridge.resolve(pid, int(idx))
        except ValueError:
            note = "Bouton inconnu."
        tg.answer_callback(cb["id"], note)
        message = cb.get("message") or {}
        if message:
            tg.remove_buttons(message["chat"]["id"], message["message_id"], f"→ {note}")

    def _telegram_file(tg: Telegram, file_id: str, filename: str, mime: str, caption: str) -> None:
        data, path = tg.download(file_id)
        if filename == "document" and path:
            filename = path.rsplit("/", 1)[-1]
        file_input("telegram", data, filename, mime, caption)

    # ------------------------------------------------------------- WhatsApp
    @app.get("/whatsapp/webhook")
    def whatsapp_verify(request: Request) -> PlainTextResponse:
        q = request.query_params
        if q.get("hub.mode") == "subscribe" and s.whatsapp_verify_token and q.get("hub.verify_token") == s.whatsapp_verify_token:
            return PlainTextResponse(q.get("hub.challenge", ""))
        raise HTTPException(status_code=403)

    @app.post("/whatsapp/webhook")
    async def whatsapp_webhook(request: Request, x_hub_signature_256: str = Header(default="")) -> dict:
        if "whatsapp" not in channels:
            raise HTTPException(status_code=404)
        wa: WhatsApp = channels["whatsapp"]  # type: ignore[assignment]
        raw = await request.body()
        if not wa.verify_signature(raw, x_hub_signature_256):
            raise HTTPException(status_code=403)
        body = await request.json()
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                for m in change.get("value", {}).get("messages", []) or []:
                    if m.get("from", "").lstrip("+") != s.owner_whatsapp_number:
                        log.warning("Message WhatsApp ignoré (expéditeur inconnu)")
                        continue
                    if not bridge.store.claim(f"wa:{m.get('id')}", "whatsapp"):
                        continue  # Meta renvoie parfois le même message
                    _run_async(_whatsapp_message, wa, m)
        return {"ok": True}

    def _whatsapp_message(wa: WhatsApp, m: dict) -> None:
        kind = m.get("type")
        if kind == "text":
            text_input("whatsapp", m["text"]["body"])
        elif kind == "interactive":
            reply = m["interactive"].get("button_reply") or m["interactive"].get("list_reply") or {}
            try:
                _, pid, idx = reply.get("id", "").split(":")
                wa.send_text(f"→ {bridge.resolve(pid, int(idx))}")
            except ValueError:
                text_input("whatsapp", reply.get("title", ""))
        elif kind in ("image", "document"):
            media = m[kind]
            data, mime = wa.download(media["id"])
            file_input("whatsapp", data, media.get("filename", f"{kind}"), media.get("mime_type", mime), media.get("caption", ""))
        elif kind in ("audio", "voice"):
            wa.send_text(VOICE_REPLY)

    # ------------------------------------------------------------- Anthropic
    @app.post("/anthropic/webhook")
    async def anthropic_webhook(request: Request) -> dict:
        raw = (await request.body()).decode()
        try:
            event = client.beta.webhooks.unwrap(raw, headers=dict(request.headers))
        except Exception:
            raise HTTPException(status_code=400, detail="signature invalide")
        if not bridge.store.claim(f"wh:{event.id}", "webhook"):
            return {"ok": True}
        dtype, did = event.data.type, event.data.id
        if dtype == "session.status_idled":
            _run_async(_on_idle, did)
        elif dtype == "deployment_run.succeeded":
            _run_async(_on_run, did)
        elif dtype == "deployment_run.failed":
            _run_async(bridge.notify, "", "Une de mes tâches planifiées n'a pas pu démarrer. Regarde la console Anthropic (Deployments).")
        elif dtype == "vault_credential.refresh_failed":
            log.warning("Échec de rafraîchissement d'un identifiant du coffre : %s", did)
        return {"ok": True}

    def _on_idle(session_id: str) -> None:
        if bridge.is_ours(session_id):
            bridge.process_idle(session_id)

    def _on_run(run_id: str) -> None:
        run = client.beta.deployment_runs.retrieve(run_id)
        if run.session_id:
            bridge.watch(run.session_id)

    return app, bridge


def create_app() -> FastAPI:
    """Fabrique utilisée par uvicorn : `uvicorn gateway.app:create_app --factory`."""
    return build()[0]
