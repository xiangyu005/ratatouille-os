"""AI database tests: schema, ownership, CRUD, cascades, and migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from db import DEFAULT_DB_PATH, AIDatabase


def raw_connect(db: AIDatabase) -> sqlite3.Connection:
    conn = sqlite3.connect(db.path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def seed(db: AIDatabase) -> tuple[str, str, str]:
    source_id = db.create_source(
        "食藥署食品營養成分資料庫",
        source_id="src-fda",
        uri="https://example.invalid/nutrition.csv",
        publisher="TFDA",
        license="政府資料開放授權條款",
    )
    document_id = db.create_document(
        source_id,
        "食品營養成分",
        document_id="doc-nutrition",
        content_hash="sha256:demo",
        metadata={"rows": 230152},
    )
    chunk_id = db.add_chunk(
        document_id,
        0,
        "小麥胚芽每 100 公克含蛋白質、膳食纖維、鉀與飽和脂肪。",
        chunk_id="chk-1",
        token_count=24,
    )
    return source_id, document_id, chunk_id


def test_schema_and_wal(tmp_path: Path) -> None:
    db = AIDatabase(tmp_path / "rag.sqlite")
    assert db.schema_version() == 1

    tables = set(db.table_names())
    assert {"sources", "documents", "chunks", "citations"} <= tables
    assert {"ingest_jobs", "agent_runs", "model_calls", "tool_calls"} <= tables
    assert {"evaluations", "index_versions"} <= tables
    # This is the AI DB, not the game DB.
    assert not {"events", "snapshots", "world", "tasks"} & tables

    with raw_connect(db) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_documents_chunks_and_citations(tmp_path: Path) -> None:
    db = AIDatabase(tmp_path / "rag.sqlite")
    _, document_id, chunk_id = seed(db)

    document = db.get_document(document_id)
    assert document is not None
    assert document["title"] == "食品營養成分"
    assert document["metadata"] == {"rows": 230152}

    chunks = db.get_chunks(document_id)
    assert len(chunks) == 1
    assert chunks[0]["id"] == chunk_id
    assert chunks[0]["metadata"] == {}

    citation_id = db.add_citation("answer-1", chunk_id, quote="小麥胚芽", score=0.91)
    assert citation_id > 0
    citations = db.get_citations("answer-1")
    assert citations[0]["chunk_id"] == chunk_id
    assert citations[0]["quote"] == "小麥胚芽"


def test_missing_source_is_rejected(tmp_path: Path) -> None:
    db = AIDatabase(tmp_path / "rag.sqlite")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_document("src-missing", "孤兒文件", document_id="doc-orphan")


def test_duplicate_chunk_index_is_rejected(tmp_path: Path) -> None:
    db = AIDatabase(tmp_path / "rag.sqlite")
    _, document_id, _ = seed(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.add_chunk(document_id, 0, "重複索引", chunk_id="chk-2")


def test_delete_document_cascades_chunks_and_citations(tmp_path: Path) -> None:
    db = AIDatabase(tmp_path / "rag.sqlite")
    _, document_id, chunk_id = seed(db)
    db.add_citation("answer-1", chunk_id)

    with raw_connect(db) as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        conn.commit()

    assert db.count_rows("documents") == 0
    assert db.count_rows("chunks") == 0
    assert db.count_rows("citations") == 0


def test_ingest_job_and_agent_run_records(tmp_path: Path) -> None:
    db = AIDatabase(tmp_path / "rag.sqlite")

    job_id = db.create_ingest_job(source_uri="nutrition.csv", total_items=3)
    db.update_ingest_job(job_id, status="running", started=True)
    db.update_ingest_job(job_id, status="done", processed_items=3, finished=True)
    assert db.count_rows("ingest_jobs") == 1

    run_id = db.create_agent_run("compare nutrition", plan={"steps": ["search"]})
    db.record_model_call(
        run_id=run_id,
        provider="ollama",
        model="phi4-mini",
        prompt_tokens=100,
        completion_tokens=40,
        latency_ms=800,
    )
    db.record_tool_call(
        run_id=run_id,
        tool_name="rag.search",
        args_hash="sha256:args",
        status="ok",
        latency_ms=12,
    )
    db.record_evaluation(metric="citation_precision", value=1.0, run_id=run_id)
    db.finish_agent_run(run_id)

    assert db.count_rows("agent_runs") == 1
    assert db.count_rows("model_calls") == 1
    assert db.count_rows("tool_calls") == 1
    assert db.count_rows("evaluations") == 1


def test_index_version_is_unique(tmp_path: Path) -> None:
    db = AIDatabase(tmp_path / "rag.sqlite")
    db.record_index_version(
        index_type="faiss",
        version="v1",
        embedding_model="multilingual-e5-small",
        path="data/ai/vectors.faiss",
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.record_index_version(index_type="faiss", version="v1")


def test_migration_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "rag.sqlite"
    first = AIDatabase(path)
    seed(first)
    second = AIDatabase(path)
    assert second.schema_version() == 1
    assert second.count_rows("documents") == 1


def test_default_path_is_ai_not_core() -> None:
    assert DEFAULT_DB_PATH.name == "rag.sqlite"
    assert "core" not in DEFAULT_DB_PATH.parts
