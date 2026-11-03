"""API contract tests for the CORE service."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from core.api.app import create_app


def make_client(path: Path) -> TestClient:
    return TestClient(create_app(path))


def test_health_and_meta(tmp_path: Path) -> None:
    client = make_client(tmp_path / "core.sqlite")

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    meta = client.get("/api/v1/meta")
    assert meta.status_code == 200
    body = meta.json()
    assert body["schema_version"] == 2
    assert {"fcfs", "sjf", "priority_aging"} <= set(body["policies"])
    assert any(item["name"] == "srtf" and not item["assignable"] for item in body["algorithms"])
    assert len(body["caching_algorithms"]) == 5
    assert len(body["memory_algorithms"]) == 3
    assert len(body["deadlock_algorithms"]) == 4


def test_command_updates_snapshot_and_tasks(tmp_path: Path) -> None:
    client = make_client(tmp_path / "core.sqlite")

    response = client.post(
        "/api/v1/commands",
        json={
            "command": "ENQUEUE_TASK",
            "args": {"name": "Soup", "burst_seconds": 3, "priority": 2},
            "idempotency_key": "k1",
            "client": "pytest",
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["accepted"] is True
    assert len(body["event_ids"]) == 1

    snapshot = client.get("/api/v1/snapshot").json()
    assert snapshot["state"]["tasks"]["T-0001"]["name"] == "Soup"
    assert snapshot["state_version"] == 1

    tasks = client.get("/api/v1/tasks").json()
    assert tasks["tasks"][0]["status"] == "queued"


def test_idempotency_key_returns_cached_result(tmp_path: Path) -> None:
    client = make_client(tmp_path / "core.sqlite")
    payload = {
        "command": "ENQUEUE_TASK",
        "args": {"burst_seconds": 1},
        "idempotency_key": "same-key",
        "client": "pytest",
    }

    first = client.post("/api/v1/commands", json=payload).json()
    second = client.post("/api/v1/commands", json=payload).json()

    assert first["event_ids"] == second["event_ids"]
    assert second["cached"] is True
    assert len(client.get("/api/v1/tasks").json()["tasks"]) == 1


def test_invalid_command_returns_contract_error(tmp_path: Path) -> None:
    client = make_client(tmp_path / "core.sqlite")

    response = client.post(
        "/api/v1/commands",
        json={
            "command": "NOT_A_COMMAND",
            "args": {},
            "idempotency_key": "k1",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["accepted"] is False
    assert body["error"]["code"] == "UNKNOWN_COMMAND"
    assert body["request_id"]


def test_busy_worker_is_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path / "core.sqlite")
    for key, name in (("k1", "A"), ("k2", "B")):
        client.post(
            "/api/v1/commands",
            json={
                "command": "ENQUEUE_TASK",
                "args": {"name": name, "burst_seconds": 2},
                "idempotency_key": key,
            },
        )
    client.post(
        "/api/v1/commands",
        json={
            "command": "ASSIGN_TASK",
            "args": {"worker_id": "W-1", "task_id": "T-0001"},
            "idempotency_key": "k3",
        },
    )

    response = client.post(
        "/api/v1/commands",
        json={
            "command": "ASSIGN_TASK",
            "args": {"worker_id": "W-1", "task_id": "T-0002"},
            "idempotency_key": "k4",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKER_BUSY"


def test_websocket_receives_snapshot_then_event(tmp_path: Path) -> None:
    client = make_client(tmp_path / "core.sqlite")

    with client.websocket_connect("/ws/events") as websocket:
        hello = websocket.receive_json()
        assert hello["type"] == "SNAPSHOT"

        response = client.post(
            "/api/v1/commands",
            json={
                "command": "ENQUEUE_TASK",
                "args": {"name": "WS", "burst_seconds": 1},
                "idempotency_key": "k1",
            },
        )
        event = websocket.receive_json()

    assert event["type"] == "TASK_ENQUEUED"
    assert event["event_id"] == response.json()["event_ids"][0]
    assert event["payload"]["task"]["name"] == "WS"
