"""SQLite persistence for the CORE event log and world snapshots.

SQLite runs in WAL mode. CORE is the only writer; every command commits the
event rows, the new snapshot and the idempotency record in one transaction.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Iterator

from core.domain.models import DomainEvent, WorldState

SCHEMA_VERSION = 1


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._tx() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    sim_time INTEGER NOT NULL,
                    state_version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    causation_id TEXT,
                    correlation_id TEXT,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                );
                CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);

                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    state_version INTEGER NOT NULL,
                    last_event_id INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                );

                CREATE TABLE IF NOT EXISTS idempotency (
                    key TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                );
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def schema_version(self) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            return int(row["value"]) if row else SCHEMA_VERSION

    def load_latest_state(self) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT state_json FROM snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            return json.loads(row["state_json"])

    def commit(
        self,
        state: WorldState,
        events: list[DomainEvent],
        idempotency_key: str,
        response: dict[str, Any],
    ) -> list[int]:
        with self._tx() as conn:
            ids: list[int] = []
            for event in events:
                cursor = conn.execute(
                    """
                    INSERT INTO events
                        (type, sim_time, state_version, payload, causation_id, correlation_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.type,
                        event.sim_time,
                        event.state_version,
                        json.dumps(event.payload, ensure_ascii=False, sort_keys=True),
                        event.causation_id,
                        event.correlation_id,
                    ),
                )
                ids.append(int(cursor.lastrowid))

            state.last_event_id = max([state.last_event_id, *ids])
            conn.execute(
                """
                INSERT INTO snapshots (state_version, last_event_id, state_json)
                VALUES (?, ?, ?)
                """,
                (
                    state.version,
                    state.last_event_id,
                    json.dumps(state.to_dict(), ensure_ascii=False, sort_keys=True),
                ),
            )

            stored = dict(response)
            stored["event_ids"] = ids
            stored["state_version"] = state.version
            conn.execute(
                "INSERT OR REPLACE INTO idempotency(key, response_json) VALUES (?, ?)",
                (idempotency_key, json.dumps(stored, ensure_ascii=False, sort_keys=True)),
            )
            return ids

    def get_idempotent(self, key: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT response_json FROM idempotency WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            return json.loads(row["response_json"])

    def get_events(self, after_id: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 1000))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, type, sim_time, state_version, payload,
                       causation_id, correlation_id, created_at
                FROM events
                WHERE id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (after_id, limit),
            ).fetchall()
            return [
                {
                    "event_id": row["id"],
                    "type": row["type"],
                    "sim_time": row["sim_time"],
                    "state_version": row["state_version"],
                    "payload": json.loads(row["payload"]),
                    "causation_id": row["causation_id"],
                    "correlation_id": row["correlation_id"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    def event_count(self) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()
            return int(row["n"])
