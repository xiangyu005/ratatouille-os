"""CORE DB must remain the game world DB, not the AI/RAG DB."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.persistence.store import Store


def test_core_db_has_no_ai_tables(tmp_path: Path) -> None:
    path = tmp_path / "core.sqlite"
    Store(path)

    conn = sqlite3.connect(path)
    try:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert {"events", "snapshots", "idempotency"} <= names
        assert not {
            "documents",
            "chunks",
            "citations",
            "agent_runs",
            "model_calls",
            "tool_calls",
        } & names
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()
