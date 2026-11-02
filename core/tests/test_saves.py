"""Save points, incremental snapshot, event filters and contract shape."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from core.api.app import create_app


def make_client(path: Path) -> TestClient:
    return TestClient(create_app(path))


def enqueue(client: TestClient, key: str, name: str, burst: int = 3) -> dict:
    response = client.post(
        "/api/v1/commands",
        json={
            "command": "ENQUEUE_TASK",
            "args": {"name": name, "burst_seconds": burst},
            "idempotency_key": key,
            "client": "pytest",
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_every_response_carries_request_id(tmp_path: Path) -> None:
    client = make_client(tmp_path / "core.sqlite")

    bodies = [
        client.get("/health").json(),
        client.get("/api/v1/meta").json(),
        client.get("/api/v1/snapshot").json(),
        client.get("/api/v1/events").json(),
        client.get("/api/v1/tasks").json(),
        client.get("/api/v1/resources").json(),
        client.get("/api/v1/saves").json(),
    ]
    for body in bodies:
        assert body["request_id"], body

    # the header and the body must agree
    response = client.get("/health", headers={"x-request-id": "req-fixed"})
    assert response.headers["x-request-id"] == "req-fixed"
    assert response.json()["request_id"] == "req-fixed"


def test_save_then_load_restores_world(tmp_path: Path) -> None:
    client = make_client(tmp_path / "core.sqlite")
    enqueue(client, "k1", "Soup")

    saved = client.post("/api/v1/save", json={"label": "before-cooking"})
    assert saved.status_code == 201, saved.text
    meta = saved.json()
    assert meta["label"] == "before-cooking"
    assert meta["state_version"] == 1
    assert len(meta["checksum"]) == 64

    enqueue(client, "k2", "Stew")
    assert len(client.get("/api/v1/tasks").json()["tasks"]) == 2

    loaded = client.post("/api/v1/load", json={"save_id": meta["save_id"]})
    assert loaded.status_code == 200, loaded.text
    body = loaded.json()
    assert body["loaded"] is True
    assert body["save_id"] == meta["save_id"]
    assert body["state_version"] == 1

    tasks = client.get("/api/v1/tasks").json()["tasks"]
    assert [task["name"] for task in tasks] == ["Soup"]

    # the world keeps working after a load
    enqueue(client, "k3", "Bread")
    assert len(client.get("/api/v1/tasks").json()["tasks"]) == 2


def test_load_latest_without_body(tmp_path: Path) -> None:
    client = make_client(tmp_path / "core.sqlite")
    enqueue(client, "k1", "Soup")
    first = client.post("/api/v1/save", json={"label": "one"}).json()
    enqueue(client, "k2", "Stew")
    second = client.post("/api/v1/save", json={"label": "two"}).json()

    assert first["save_id"] < second["save_id"]

    saves = client.get("/api/v1/saves").json()["saves"]
    assert [item["label"] for item in saves] == ["two", "one"]

    latest = client.post("/api/v1/load").json()
    assert latest["save_id"] == second["save_id"]
    assert latest["label"] == "two"


def test_load_missing_save_returns_contract_error(tmp_path: Path) -> None:
    client = make_client(tmp_path / "core.sqlite")

    response = client.post("/api/v1/load", json={"save_id": 999})
    assert response.status_code == 404
    body = response.json()
    assert body["accepted"] is False
    assert body["error"]["code"] == "SAVE_NOT_FOUND"

    # no save at all -> still a contract error, not a 500
    empty = client.post("/api/v1/load")
    assert empty.status_code == 404
    assert empty.json()["error"]["code"] == "SAVE_NOT_FOUND"


def test_corrupted_save_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "core.sqlite"
    client = make_client(path)
    enqueue(client, "k1", "Soup")
    save_id = client.post("/api/v1/save", json={}).json()["save_id"]

    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "UPDATE saves SET state_json = '{}' WHERE id = ?", (save_id,)
        )
        conn.commit()
    finally:
        conn.close()

    response = client.post("/api/v1/load", json={"save_id": save_id})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SAVE_CORRUPTED"


def test_save_is_visible_to_websocket_clients(tmp_path: Path) -> None:
    client = make_client(tmp_path / "core.sqlite")
    enqueue(client, "k1", "Soup")
    save_id = client.post("/api/v1/save", json={}).json()["save_id"]
    enqueue(client, "k2", "Stew")

    with client.websocket_connect("/ws/events") as websocket:
        assert websocket.receive_json()["type"] == "SNAPSHOT"
        client.post("/api/v1/load", json={"save_id": save_id})
        message = websocket.receive_json()

    assert message["type"] == "SNAPSHOT"
    assert message["reason"] == "save_loaded"
    assert list(message["state"]["tasks"]) == ["T-0001"]


def test_snapshot_since_event_id_is_incremental(tmp_path: Path) -> None:
    client = make_client(tmp_path / "core.sqlite")
    first = enqueue(client, "k1", "Soup")
    second = enqueue(client, "k2", "Stew")

    full = client.get("/api/v1/snapshot").json()
    assert full["events"] is None

    incremental = client.get(
        "/api/v1/snapshot", params={"since_event_id": first["event_ids"][0]}
    ).json()
    assert incremental["state_version"] == 2
    assert [event["event_id"] for event in incremental["events"]] == second["event_ids"]


def test_event_filters(tmp_path: Path) -> None:
    client = make_client(tmp_path / "core.sqlite")
    enqueue(client, "k1", "Soup")
    client.post(
        "/api/v1/commands",
        json={
            "command": "ADVANCE_TIME",
            "args": {"seconds": 10},
            "idempotency_key": "k2",
        },
    )

    by_type = client.get("/api/v1/events", params={"type": "TIME_ADVANCED"}).json()
    assert [event["type"] for event in by_type["events"]] == ["TIME_ADVANCED"]

    by_time = client.get(
        "/api/v1/events", params={"from_sim_time": 5, "to_sim_time": 20}
    ).json()
    assert [event["type"] for event in by_time["events"]] == ["TIME_ADVANCED"]
    assert by_time["last_event_id"] == 2
