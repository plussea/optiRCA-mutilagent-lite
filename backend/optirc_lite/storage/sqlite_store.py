import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from optirc_lite.config import settings


class SQLiteStore:
    """Tiny local persistence layer for sessions and runtime traces."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.database_path

    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def upsert_session(self, session_id: str, status: str, state: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(state, ensure_ascii=False)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO sessions(session_id, status, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    status = excluded.status,
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (session_id, status, payload, now, now),
            )

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT state_json FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def add_event(self, session_id: str, phase: str, payload: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO events(session_id, phase, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (session_id, phase, json.dumps(payload, ensure_ascii=False), now),
            )

    def list_events(self, session_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                """
                SELECT phase, payload_json, created_at
                FROM events
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        return [
            {"phase": phase, "payload": json.loads(payload), "created_at": created_at}
            for phase, payload, created_at in rows
        ]


store = SQLiteStore()
