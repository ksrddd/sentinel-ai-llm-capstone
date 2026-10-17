"""SQLite persistence: synthetic incident history (read-only seed) and saved analyses.

All SQL uses bound parameters; no user input is interpolated into statements.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS incident_history (
    case_id TEXT PRIMARY KEY, opened TEXT, incident_type TEXT, hostname TEXT,
    severity TEXT, summary TEXT, resolution TEXT, closure_code TEXT
);
CREATE TABLE IF NOT EXISTS analyses (
    incident_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, label TEXT,
    incident_type TEXT, severity TEXT, requires_review INTEGER, payload TEXT NOT NULL
);
"""


class IncidentRepository:
    def __init__(self, db_path: Path, history_seed: Path | None = None) -> None:
        self._lock = threading.Lock()
        if str(db_path) != ":memory:":
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            if history_seed and history_seed.is_file():
                self._seed(history_seed)

    def _seed(self, path: Path) -> None:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self._conn.executemany(
            "INSERT OR REPLACE INTO incident_history VALUES "
            "(:case_id,:opened,:incident_type,:hostname,:severity,:summary,:resolution,:closure_code)", rows)
        self._conn.commit()

    def search_history(self, hostname: str | None = None, incident_type: str | None = None,
                       limit: int = 5) -> list[dict]:
        clauses, params = [], []
        if hostname:
            clauses.append("UPPER(hostname) = UPPER(?)")
            params.append(hostname)
        if incident_type:
            clauses.append("incident_type = ?")
            params.append(incident_type)
        where = (" WHERE " + (" OR " if hostname and incident_type else "").join(clauses)) if clauses else ""
        sql = f"SELECT * FROM incident_history{where} ORDER BY opened DESC LIMIT ?"  # noqa: S608 - fixed fragments only
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, [*params, int(limit)])]

    def save_analysis(self, incident_id: str, label: str | None, incident_type: str, severity: str,
                      requires_review: bool, payload: dict) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO analyses VALUES (?,?,?,?,?,?,?)",
                (incident_id, datetime.now(UTC).isoformat(timespec="seconds"), label, incident_type,
                 severity, int(requires_review), json.dumps(payload, default=str)))
            self._conn.commit()

    def list_analyses(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT incident_id, created_at, label, incident_type, severity, requires_review "
                "FROM analyses ORDER BY created_at DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]

    def get_analysis(self, incident_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT payload FROM analyses WHERE incident_id = ?",
                                     (incident_id,)).fetchone()
        return json.loads(row["payload"]) if row else None
