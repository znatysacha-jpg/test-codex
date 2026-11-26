"""Petit état local (SQLite) : session principale, événements déjà traités, validations en attente."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claims (event_id TEXT PRIMARY KEY, kind TEXT, at REAL);
CREATE TABLE IF NOT EXISTS pending (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    event_id TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,          -- 'custom' (outil maison) ou 'confirm' (outil intégré en attente)
    tool_name TEXT NOT NULL,
    input_json TEXT NOT NULL,
    options_json TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    at REAL
);
-- Historique affiché dans l'app (tous canaux confondus)
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,          -- 'agent' ou 'user'
    kind TEXT NOT NULL,          -- 'text', 'choices', 'whatsapp', 'options', 'file'
    text TEXT NOT NULL DEFAULT '',
    data_json TEXT NOT NULL DEFAULT '{}',
    channel TEXT NOT NULL DEFAULT '',
    at REAL
);
CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY, filename TEXT NOT NULL, data BLOB NOT NULL, at REAL);
"""


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)

    # --- clé / valeur -------------------------------------------------
    def get(self, key: str) -> Optional[str]:
        with self._lock:
            row = self._db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO kv(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def delete(self, key: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM kv WHERE key=?", (key,))

    # --- traitement unique des événements -------------------------------
    def claim(self, event_id: str, kind: str = "") -> bool:
        """Renvoie True une seule fois par événement, même si plusieurs fils le voient."""
        with self._lock:
            cur = self._db.execute(
                "INSERT OR IGNORE INTO claims(event_id, kind, at) VALUES(?, ?, ?)", (event_id, kind, time.time())
            )
            return cur.rowcount == 1

    def is_claimed(self, event_id: str) -> bool:
        with self._lock:
            return self._db.execute("SELECT 1 FROM claims WHERE event_id=?", (event_id,)).fetchone() is not None

    # --- validations en attente ----------------------------------------
    def add_pending(
        self, session_id: str, event_id: str, kind: str, tool_name: str, tool_input: dict, options: list[str], channel: str
    ) -> Optional[str]:
        pid = uuid.uuid4().hex[:10]
        with self._lock:
            cur = self._db.execute(
                "INSERT OR IGNORE INTO pending(id, session_id, event_id, kind, tool_name, input_json, options_json, channel, at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (pid, session_id, event_id, kind, tool_name, json.dumps(tool_input), json.dumps(options), channel, time.time()),
            )
        return pid if cur.rowcount == 1 else None

    def get_pending(self, pid: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self._db.execute("SELECT * FROM pending WHERE id=?", (pid,)).fetchone()
        return self._row(row)

    def open_pending(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM pending WHERE status='open' ORDER BY at").fetchall()
        return [self._row(r) for r in rows]

    def close_pending(self, pid: str, status: str) -> bool:
        """Ferme une validation ; renvoie False si elle était déjà fermée (double clic)."""
        with self._lock:
            cur = self._db.execute("UPDATE pending SET status=? WHERE id=? AND status='open'", (status, pid))
            return cur.rowcount == 1

    # --- historique de l'app ---------------------------------------------
    def add_message(self, role: str, kind: str, text: str = "", data: Optional[dict] = None, channel: str = "") -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO messages(role, kind, text, data_json, channel, at) VALUES(?,?,?,?,?,?)",
                (role, kind, text, json.dumps(data or {}, ensure_ascii=False), channel, time.time()),
            )
            return int(cur.lastrowid)

    def messages_after(self, after_id: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            if after_id <= 0:
                rows = self._db.execute("SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
                rows = list(reversed(rows))
            else:
                rows = self._db.execute("SELECT * FROM messages WHERE id > ? ORDER BY id LIMIT ?", (after_id, limit)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["data"] = json.loads(d.pop("data_json"))
            out.append(d)
        return out

    def last_message_id(self) -> int:
        with self._lock:
            row = self._db.execute("SELECT COALESCE(MAX(id), 0) AS m FROM messages").fetchone()
        return int(row["m"])

    def put_file(self, file_id: str, filename: str, data: bytes) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO files(id, filename, data, at) VALUES(?,?,?,?)", (file_id, filename, data, time.time())
            )

    def get_file(self, file_id: str) -> Optional[tuple[str, bytes]]:
        with self._lock:
            row = self._db.execute("SELECT filename, data FROM files WHERE id=?", (file_id,)).fetchone()
        return (row["filename"], bytes(row["data"])) if row else None

    @staticmethod
    def _row(row) -> Optional[dict[str, Any]]:
        if row is None:
            return None
        d = dict(row)
        d["input"] = json.loads(d.pop("input_json"))
        d["options"] = json.loads(d.pop("options_json"))
        return d
