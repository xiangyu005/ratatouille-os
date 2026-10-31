"""AI-owned SQLite database.

This database is separate from the CORE/game database on purpose:

- `data/core/core.sqlite` is the authoritative game world, owned by CORE.
- `data/ai/rag.sqlite` stores documents, chunks, citations, ingest jobs and
  AI execution records, owned by AI.

There are no cross-database joins. AI may keep CORE identifiers as opaque
references, but must read game state through the Core API.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "ai" / "rag.sqlite"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    uri TEXT,
    publisher TEXT,
    license TEXT,
    retrieved_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1',
    content_hash TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (source_id, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source_id);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL CHECK (length(text) > 0),
    token_count INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);

CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    answer_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    quote TEXT,
    score REAL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_citations_answer ON citations(answer_id);

CREATE TABLE IF NOT EXISTS ingest_jobs (
    id TEXT PRIMARY KEY,
    source_uri TEXT,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'done', 'failed')),
    total_items INTEGER NOT NULL DEFAULT 0,
    processed_items INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    task TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'done', 'failed')),
    plan_json TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS model_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT REFERENCES agent_runs(id) ON DELETE SET NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    latency_ms INTEGER,
    cost_usd REAL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_model_calls_run ON model_calls(run_id);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT REFERENCES agent_runs(id) ON DELETE SET NULL,
    tool_name TEXT NOT NULL,
    args_hash TEXT,
    status TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    latency_ms INTEGER,
    result_summary TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(run_id);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evaluations_metric ON evaluations(metric);

CREATE TABLE IF NOT EXISTS index_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_type TEXT NOT NULL CHECK (index_type IN ('faiss', 'bm25s')),
    embedding_model TEXT,
    version TEXT NOT NULL,
    path TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (index_type, version)
);
"""

MIGRATIONS: dict[int, str] = {1: SCHEMA_SQL}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _json(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    return json.loads(value)


class AIDatabase:
    """Thin SQLite repository for AI-owned metadata.

    Connections are short-lived; every write is a transaction. WAL and foreign
    keys are enabled on every connection.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        raw = path or os.getenv("AI_DB_PATH") or DEFAULT_DB_PATH
        resolved = Path(raw).expanduser()
        if not resolved.is_absolute():
            resolved = PROJECT_ROOT / resolved
        self.path = resolved
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def migrate(self) -> None:
        with self._tx() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
            ).fetchone()
            current = int(row["version"])
            if current > SCHEMA_VERSION:
                raise RuntimeError(
                    f"AI DB schema {current} is newer than supported {SCHEMA_VERSION}"
                )
            for version in sorted(MIGRATIONS):
                if version > current:
                    conn.executescript(MIGRATIONS[version])
                    conn.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (version, _now()),
                    )

    def schema_version(self) -> int:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
            ).fetchone()
            return int(row["version"])

    def table_names(self) -> list[str]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            return sorted(row["name"] for row in rows)

    def create_source(
        self,
        name: str,
        *,
        source_id: str | None = None,
        uri: str | None = None,
        publisher: str | None = None,
        license: str | None = None,
        metadata: dict[str, Any] | None = None,
        retrieved_at: str | None = None,
    ) -> str:
        source_id = source_id or f"src-{uuid.uuid4().hex[:12]}"
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO sources
                    (id, name, uri, publisher, license, retrieved_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    uri=excluded.uri,
                    publisher=excluded.publisher,
                    license=excluded.license,
                    retrieved_at=excluded.retrieved_at,
                    metadata_json=excluded.metadata_json
                """,
                (
                    source_id,
                    name,
                    uri,
                    publisher,
                    license,
                    retrieved_at or _now(),
                    _json(metadata),
                ),
            )
        return source_id

    def create_document(
        self,
        source_id: str,
        title: str,
        *,
        document_id: str | None = None,
        version: str = "1",
        content_hash: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        document_id = document_id or f"doc-{uuid.uuid4().hex[:12]}"
        now = _now()
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO documents
                    (id, source_id, title, version, content_hash,
                     metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_id=excluded.source_id,
                    title=excluded.title,
                    version=excluded.version,
                    content_hash=excluded.content_hash,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    document_id,
                    source_id,
                    title,
                    version,
                    content_hash,
                    _json(metadata),
                    now,
                    now,
                ),
            )
        return document_id

    def add_chunk(
        self,
        document_id: str,
        chunk_index: int,
        text: str,
        *,
        chunk_id: str | None = None,
        token_count: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        chunk_id = chunk_id or f"chk-{uuid.uuid4().hex[:12]}"
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO chunks
                    (id, document_id, chunk_index, text, token_count,
                     metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    document_id,
                    chunk_index,
                    text,
                    token_count,
                    _json(metadata),
                    _now(),
                ),
            )
        return chunk_id

    def add_citation(
        self,
        answer_id: str,
        chunk_id: str,
        *,
        quote: str | None = None,
        score: float | None = None,
    ) -> int:
        with self._tx() as conn:
            cursor = conn.execute(
                """
                INSERT INTO citations (answer_id, chunk_id, quote, score, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (answer_id, chunk_id, quote, score, _now()),
            )
            return int(cursor.lastrowid)

    def create_ingest_job(
        self,
        *,
        job_id: str | None = None,
        source_uri: str | None = None,
        total_items: int = 0,
        status: str = "queued",
    ) -> str:
        job_id = job_id or f"job-{uuid.uuid4().hex[:12]}"
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO ingest_jobs
                    (id, source_uri, status, total_items, processed_items, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (job_id, source_uri, status, total_items, _now()),
            )
        return job_id

    def update_ingest_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        processed_items: int | None = None,
        error: str | None = None,
        started: bool = False,
        finished: bool = False,
    ) -> None:
        fields: list[str] = []
        values: list[Any] = []
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if processed_items is not None:
            fields.append("processed_items = ?")
            values.append(processed_items)
        if error is not None:
            fields.append("error = ?")
            values.append(error)
        if started:
            fields.append("started_at = ?")
            values.append(_now())
        if finished:
            fields.append("finished_at = ?")
            values.append(_now())
        if not fields:
            return
        values.append(job_id)
        with self._tx() as conn:
            conn.execute(
                f"UPDATE ingest_jobs SET {', '.join(fields)} WHERE id = ?", values
            )

    def create_agent_run(
        self,
        task: str,
        *,
        run_id: str | None = None,
        status: str = "running",
        plan: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO agent_runs
                    (id, task, status, plan_json, started_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    task,
                    status,
                    json.dumps(plan, ensure_ascii=False, sort_keys=True)
                    if plan is not None
                    else None,
                    _now(),
                    _json(metadata),
                ),
            )
        return run_id

    def finish_agent_run(self, run_id: str, *, status: str = "done") -> None:
        with self._tx() as conn:
            conn.execute(
                "UPDATE agent_runs SET status = ?, finished_at = ? WHERE id = ?",
                (status, _now(), run_id),
            )

    def record_model_call(
        self,
        *,
        run_id: str | None,
        provider: str,
        model: str,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        latency_ms: int | None = None,
        cost_usd: float | None = None,
    ) -> int:
        with self._tx() as conn:
            cursor = conn.execute(
                """
                INSERT INTO model_calls
                    (run_id, provider, model, prompt_tokens, completion_tokens,
                     latency_ms, cost_usd, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    provider,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    latency_ms,
                    cost_usd,
                    _now(),
                ),
            )
            return int(cursor.lastrowid)

    def record_tool_call(
        self,
        *,
        run_id: str | None,
        tool_name: str,
        args_hash: str | None = None,
        status: str = "ok",
        latency_ms: int | None = None,
        result_summary: str | None = None,
    ) -> int:
        with self._tx() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tool_calls
                    (run_id, tool_name, args_hash, status, latency_ms,
                     result_summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    tool_name,
                    args_hash,
                    status,
                    latency_ms,
                    result_summary,
                    _now(),
                ),
            )
            return int(cursor.lastrowid)

    def record_evaluation(
        self,
        *,
        metric: str,
        value: float,
        run_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        with self._tx() as conn:
            cursor = conn.execute(
                """
                INSERT INTO evaluations (run_id, metric, value, details_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, metric, value, _json(details), _now()),
            )
            return int(cursor.lastrowid)

    def record_index_version(
        self,
        *,
        index_type: str,
        version: str,
        embedding_model: str | None = None,
        path: str | None = None,
    ) -> int:
        with self._tx() as conn:
            cursor = conn.execute(
                """
                INSERT INTO index_versions
                    (index_type, embedding_model, version, path, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (index_type, embedding_model, version, path, _now()),
            )
            return int(cursor.lastrowid)

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["metadata"] = _dict(result.pop("metadata_json"))
            return result

    def get_chunks(self, document_id: str) -> list[dict[str, Any]]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
                (document_id,),
            ).fetchall()
            chunks: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                item["metadata"] = _dict(item.pop("metadata_json"))
                chunks.append(item)
            return chunks

    def get_citations(self, answer_id: str) -> list[dict[str, Any]]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT * FROM citations WHERE answer_id = ? ORDER BY id",
                (answer_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def count_rows(self, table: str) -> int:
        allowed = {
            "sources",
            "documents",
            "chunks",
            "citations",
            "ingest_jobs",
            "agent_runs",
            "model_calls",
            "tool_calls",
            "evaluations",
            "index_versions",
        }
        if table not in allowed:
            raise ValueError(f"unknown table: {table}")
        with self._tx() as conn:
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            return int(row["n"])
