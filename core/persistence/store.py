"""SQLite persistence for the CORE event log, world snapshots and saves.

SQLite runs in WAL mode. CORE is the only writer; every command commits the
event rows, the new snapshot and the idempotency record in one transaction.

The connection is opened once and reused (``docs/17`` §11.4 requires the CORE
tick budget to stay small). Opening a fresh connection per call cost ~1.5 ms
because ``PRAGMA journal_mode=WAL`` has to attach the WAL on every connection,
and closing the last connection checkpointed the WAL away again; that alone was
most of a ~11 ms command. One pinned connection with the PRAGMAs applied once
keeps a command's storage cost well under 1 ms.

``sqlite3`` connections are not thread safe, and FastAPI runs the ``def``
routes in a threadpool while commands run on the event loop, so every public
method takes ``self._lock`` before touching the connection.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from core.domain.models import DomainEvent, WorldState

SCHEMA_VERSION = 2


def _checksum(payload: str) -> str:
    """Stable checksum for a serialized world state."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _save_meta(row: sqlite3.Row) -> dict[str, Any]:
    """Save metadata as the API exposes it (``id`` -> ``save_id``)."""
    return {
        "save_id": row["id"],
        "schema_version": row["schema_version"],
        "state_version": row["state_version"],
        "last_event_id": row["last_event_id"],
        "label": row["label"],
        "checksum": row["checksum"],
        "created_at": row["created_at"],
    }


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        with self._lock:
            if self._conn is None:
                conn = sqlite3.connect(
                    self.path, timeout=5.0, check_same_thread=False
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA busy_timeout=5000")
                conn.execute("PRAGMA foreign_keys=ON")
                self._conn = conn
            return self._conn

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = self._connect()
            with conn:
                yield conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

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
                CREATE INDEX IF NOT EXISTS idx_events_sim_time ON events(sim_time);

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

                CREATE TABLE IF NOT EXISTS saves (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schema_version INTEGER NOT NULL,
                    state_version INTEGER NOT NULL,
                    last_event_id INTEGER NOT NULL,
                    label TEXT,
                    state_json TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                );
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'schema_version' AND value <> ?",
                (str(SCHEMA_VERSION), str(SCHEMA_VERSION)),
            )

    def schema_version(self) -> int:
        with self._lock:
            row = self._connect().execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
        return int(row["value"]) if row else SCHEMA_VERSION

    def load_latest_state(self) -> dict[str, Any] | None:
        with self._lock:
            row = self._connect().execute(
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
        with self._lock:
            row = self._connect().execute(
                "SELECT response_json FROM idempotency WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["response_json"])

    def get_events(
        self,
        after_id: int = 0,
        limit: int = 100,
        *,
        event_type: str | None = None,
        from_sim_time: int | None = None,
        to_sim_time: int | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 1000))
        clauses = ["id > ?"]
        params: list[Any] = [after_id]
        if event_type:
            clauses.append("type = ?")
            params.append(event_type)
        if from_sim_time is not None:
            clauses.append("sim_time >= ?")
            params.append(from_sim_time)
        if to_sim_time is not None:
            clauses.append("sim_time <= ?")
            params.append(to_sim_time)
        params.append(limit)

        with self._lock:
            rows = self._connect().execute(
                f"""
                SELECT id, type, sim_time, state_version, payload,
                       causation_id, correlation_id, created_at
                FROM events
                WHERE {" AND ".join(clauses)}
                ORDER BY id ASC
                LIMIT ?
                """,
                params,
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
        with self._lock:
            row = self._connect().execute("SELECT COUNT(*) AS n FROM events").fetchone()
        return int(row["n"])

    # -- saves -------------------------------------------------------------

    def create_save(
        self, state: WorldState, *, label: str | None = None
    ) -> dict[str, Any]:
        """Persist a manual save point; returns its metadata (no state payload)."""
        payload = json.dumps(state.to_dict(), ensure_ascii=False, sort_keys=True)
        digest = _checksum(payload)
        with self._tx() as conn:
            cursor = conn.execute(
                """
                INSERT INTO saves
                    (schema_version, state_version, last_event_id, label, state_json, checksum)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    SCHEMA_VERSION,
                    state.version,
                    state.last_event_id,
                    label,
                    payload,
                    digest,
                ),
            )
            save_id = int(cursor.lastrowid)
            row = conn.execute(
                "SELECT id, schema_version, state_version, last_event_id, label, "
                "checksum, created_at FROM saves WHERE id = ?",
                (save_id,),
            ).fetchone()
        return _save_meta(row)

    def get_save(self, save_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._connect().execute(
                "SELECT id, schema_version, state_version, last_event_id, label, "
                "state_json, checksum, created_at FROM saves WHERE id = ?",
                (save_id,),
            ).fetchone()
        if row is None:
            return None
        meta = _save_meta(row)
        meta["state_json"] = row["state_json"]
        return meta

    def latest_save(self) -> dict[str, Any] | None:
        with self._lock:
            row = self._connect().execute(
                "SELECT id, schema_version, state_version, last_event_id, label, "
                "state_json, checksum, created_at FROM saves ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        meta = _save_meta(row)
        meta["state_json"] = row["state_json"]
        return meta

    def list_saves(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        with self._lock:
            rows = self._connect().execute(
                "SELECT id, schema_version, state_version, last_event_id, label, "
                "checksum, created_at FROM saves ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_save_meta(row) for row in rows]

    def load_save(self, save_id: int | None = None) -> dict[str, Any]:
        """Return a saved state after verifying its checksum.

        Raises ``LookupError`` when the save does not exist and ``ValueError``
        when the payload no longer matches its recorded checksum.
        """
        row = self.get_save(save_id) if save_id is not None else self.latest_save()
        if row is None:
            raise LookupError(f"save {save_id} not found" if save_id else "no saves")

        payload = row["state_json"]
        if _checksum(payload) != row["checksum"]:
            raise ValueError(f"save {row['save_id']} is corrupted (checksum mismatch)")
        return {
            "save_id": row["save_id"],
            "schema_version": row["schema_version"],
            "state_version": row["state_version"],
            "last_event_id": row["last_event_id"],
            "label": row["label"],
            "created_at": row["created_at"],
            "state": json.loads(payload),
        }
