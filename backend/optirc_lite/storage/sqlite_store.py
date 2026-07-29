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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dossiers (
                    dossier_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    evidence_graph_json TEXT NOT NULL,
                    top_candidate_json TEXT,
                    critic_verdict TEXT,
                    degradation_reason TEXT,
                    confidence REAL NOT NULL,
                    requires_human_review INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def upsert_dossier(
        self,
        dossier_id: str,
        session_id: str,
        status: str,
        input_payload: Dict[str, Any],
        evidence_graph: Dict[str, Any],
        top_candidate: Dict[str, Any] | None,
        critic_verdict: str | None,
        degradation_reason: str | None,
        confidence: float,
        requires_human_review: bool,
    ) -> None:
        self.init()
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(input_payload, ensure_ascii=False)
        graph_json = json.dumps(evidence_graph, ensure_ascii=False)
        candidate_json = json.dumps(top_candidate, ensure_ascii=False) if top_candidate else None
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO dossiers(
                    dossier_id, session_id, status, input_json, evidence_graph_json,
                    top_candidate_json, critic_verdict, degradation_reason,
                    confidence, requires_human_review, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dossier_id) DO UPDATE SET
                    status = excluded.status,
                    evidence_graph_json = excluded.evidence_graph_json,
                    top_candidate_json = excluded.top_candidate_json,
                    critic_verdict = excluded.critic_verdict,
                    degradation_reason = excluded.degradation_reason,
                    confidence = excluded.confidence,
                    requires_human_review = excluded.requires_human_review,
                    updated_at = excluded.updated_at
                """,
                (
                    dossier_id,
                    session_id,
                    status,
                    payload,
                    graph_json,
                    candidate_json,
                    critic_verdict,
                    degradation_reason,
                    confidence,
                    1 if requires_human_review else 0,
                    now,
                    now,
                ),
            )

    def get_dossier(self, dossier_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT * FROM dossiers WHERE dossier_id = ?",
                (dossier_id,),
            ).fetchone()
            columns = [desc[0] for desc in conn.execute("SELECT * FROM dossiers LIMIT 0").description]
        if row is None:
            return None
        return {col: json.loads(val) if col.endswith("_json") and val is not None else val for col, val in zip(columns, row)}

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
