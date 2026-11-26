"""Gmail et Google Agenda, exécutés par la passerelle (les jetons Google ne vont jamais dans le conteneur de l'agent)."""

from __future__ import annotations

import base64
import html
import re
from email.mime.text import MIMEText
from typing import Any

from .config import Settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]
MAX_BODY_CHARS = 20000


class GoogleNotConfigured(RuntimeError):
    pass


class Google:
    def __init__(self, settings: Settings):
        self.s = settings
        self._gmail = None
        self._calendar = None

    # --- clients --------------------------------------------------------
    def _creds(self):
        if not self.s.google_enabled:
            raise GoogleNotConfigured(
                "Google n'est pas connecté. Lance `python scripts/google_auth.py` puis renseigne GOOGLE_REFRESH_TOKEN."
            )
        from google.oauth2.credentials import Credentials

        return Credentials(
            token=None,
            refresh_token=self.s.google_refresh_token,
            client_id=self.s.google_client_id,
            client_secret=self.s.google_client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )

    @property
    def gmail(self):
        if self._gmail is None:
            from googleapiclient.discovery import build

            self._gmail = build("gmail", "v1", credentials=self._creds(), cache_discovery=False)
        return self._gmail

    @property
    def calendar(self):
        if self._calendar is None:
            from googleapiclient.discovery import build

            self._calendar = build("calendar", "v3", credentials=self._creds(), cache_discovery=False)
        return self._calendar

    # --- Gmail ----------------------------------------------------------
    def gmail_search(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        max_results = max(1, min(int(max_results or 10), 25))
        resp = self.gmail.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        out = []
        for m in resp.get("messages", []):
            msg = (
                self.gmail.users()
                .messages()
                .get(userId="me", id=m["id"], format="metadata", metadataHeaders=["From", "To", "Cc", "Subject", "Date"])
                .execute()
            )
            headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
            out.append(
                {
                    "id": msg["id"],
                    "thread_id": msg.get("threadId"),
                    "de": headers.get("from", ""),
                    "a": headers.get("to", ""),
                    "objet": headers.get("subject", ""),
                    "date": headers.get("date", ""),
                    "non_lu": "UNREAD" in msg.get("labelIds", []),
                    "extrait": html.unescape(msg.get("snippet", "")),
                }
            )
        return out

    def gmail_read(self, message_id: str) -> dict[str, Any]:
        msg = self.gmail.users().messages().get(userId="me", id=message_id, format="full").execute()
        payload = msg.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
        body = _extract_text(payload)
        if len(body) > MAX_BODY_CHARS:
            body = body[:MAX_BODY_CHARS] + "\n[… e-mail tronqué]"
        attachments = [p.get("filename") for p in _walk(payload) if p.get("filename")]
        return {
            "id": msg["id"],
            "thread_id": msg.get("threadId"),
            "de": headers.get("from", ""),
            "a": headers.get("to", ""),
            "cc": headers.get("cc", ""),
            "objet": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "pieces_jointes": attachments,
            "contenu": f'<contenu_externe source="email">\n{body}\n</contenu_externe>',
        }

    def _raw(self, to: str, subject: str, body: str, cc: str = "") -> str:
        mime = MIMEText(body, "plain", "utf-8")
        mime["To"] = to
        mime["Subject"] = subject
        if cc:
            mime["Cc"] = cc
        return base64.urlsafe_b64encode(mime.as_bytes()).decode()

    def gmail_draft(self, to: str, subject: str, body: str, cc: str = "", thread_id: str = "") -> dict[str, Any]:
        message: dict[str, Any] = {"raw": self._raw(to, subject, body, cc)}
        if thread_id:
            message["threadId"] = thread_id
        draft = self.gmail.users().drafts().create(userId="me", body={"message": message}).execute()
        return {"brouillon_id": draft["id"], "statut": "brouillon créé, rien n'a été envoyé"}

    def gmail_send(self, to: str, subject: str, body: str, cc: str = "", thread_id: str = "") -> dict[str, Any]:
        message: dict[str, Any] = {"raw": self._raw(to, subject, body, cc)}
        if thread_id:
            message["threadId"] = thread_id
        sent = self.gmail.users().messages().send(userId="me", body=message).execute()
        return {"message_id": sent["id"], "statut": "envoyé"}

    # --- Agenda ---------------------------------------------------------
    def calendar_list(self, time_min: str, time_max: str, max_results: int = 50) -> list[dict[str, Any]]:
        resp = (
            self.calendar.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=max(1, min(int(max_results or 50), 250)),
                timeZone=self.s.timezone,
            )
            .execute()
        )
        out = []
        for e in resp.get("items", []):
            out.append(
                {
                    "id": e.get("id"),
                    "titre": e.get("summary", "(sans titre)"),
                    "debut": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
                    "fin": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
                    "lieu": e.get("location", ""),
                    "participants": [a.get("email") for a in e.get("attendees", []) if a.get("email")],
                    "lien_visio": e.get("hangoutLink", ""),
                }
            )
        return out

    def calendar_create(
        self, summary: str, start: str, end: str, attendees: list[str] | None = None, location: str = "", description: str = ""
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": start, "timeZone": self.s.timezone},
            "end": {"dateTime": end, "timeZone": self.s.timezone},
        }
        if location:
            event["location"] = location
        if description:
            event["description"] = description
        if attendees:
            event["attendees"] = [{"email": a} for a in attendees]
        created = (
            self.calendar.events()
            .insert(calendarId="primary", body=event, sendUpdates="all" if attendees else "none")
            .execute()
        )
        return {"event_id": created["id"], "lien": created.get("htmlLink", ""), "statut": "événement créé"}


def _walk(part: dict) -> list[dict]:
    parts = [part]
    for p in part.get("parts", []) or []:
        parts.extend(_walk(p))
    return parts


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _extract_text(payload: dict) -> str:
    plain, rich = [], []
    for p in _walk(payload):
        data = p.get("body", {}).get("data")
        if not data or p.get("filename"):
            continue
        if p.get("mimeType") == "text/plain":
            plain.append(_decode(data))
        elif p.get("mimeType") == "text/html":
            rich.append(_html_to_text(_decode(data)))
    return "\n".join(plain or rich).strip()


def _html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", "", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = html.unescape(raw)
    return re.sub(r"\n{3,}", "\n\n", raw)
