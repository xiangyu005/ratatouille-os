"""Tests for chained dish preparation workflow (Fetch -> Cook -> Serve) and Order management."""

from __future__ import annotations

import asyncio
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from core.api.app import create_app
from core.domain.errors import DomainError
from core.domain.models import Command, OrderStatus, TaskStage, TaskStatus, WorldState
from core.persistence.store import Store
from core.simulation.engine import WorldEngine


def setup_engine(tmp_path: Path) -> WorldEngine:
    store = Store(tmp_path / "test_workflow.sqlite")
    state = WorldState.new(seed=42)
    return WorldEngine(state, store)


def test_create_order_decomposes_into_chained_tasks(tmp_path: Path) -> None:
    async def scenario() -> None:
        engine = setup_engine(tmp_path)

        cmd = Command(
            command="CREATE_ORDER",
            args={"dish_name": "番茄湯", "priority": 1},
            idempotency_key="cmd-order-1",
        )
        result, events = await engine.execute(cmd)

        assert result.accepted is True
        assert "O-0001" in engine.state.orders
        order = engine.state.orders["O-0001"]
        assert order.dish_name == "番茄湯"
        assert order.status == OrderStatus.IN_PROGRESS
        assert len(order.task_ids) == 3

        t1, t2, t3 = [engine.state.tasks[tid] for tid in order.task_ids]
        # First stage (FETCH) must be immediately QUEUED
        assert t1.stage == TaskStage.FETCH
        assert t1.status == TaskStatus.QUEUED
        assert t1.prerequisite_task_id is None
        assert t1.preferred_station_id == "S-1"

        # Second stage (COOK) must be WAITING on FETCH
        assert t2.stage == TaskStage.COOK
        assert t2.status == TaskStatus.WAITING
        assert t2.prerequisite_task_id == t1.id
        assert t2.preferred_station_id == "S-2"

        # Third stage (SERVE) must be WAITING on COOK
        assert t3.stage == TaskStage.SERVE
        assert t3.status == TaskStatus.WAITING
        assert t3.prerequisite_task_id == t2.id

        # Verify events
        event_types = [e.type for e in events]
        assert event_types == ["ORDER_CREATED", "TASK_ENQUEUED"]

    asyncio.run(scenario())


def test_chained_workflow_stage_progression_to_completion(tmp_path: Path) -> None:
    async def scenario() -> None:
        engine = setup_engine(tmp_path)

        # 1. Create order for 番茄湯 (3s FETCH, 6s COOK, 2s SERVE)
        await engine.execute(
            Command(command="CREATE_ORDER", args={"dish_name": "番茄湯"}, idempotency_key="o1")
        )
        order = engine.state.orders["O-0001"]
        t1_id, t2_id, t3_id = order.task_ids

        # 2. Schedule queue: only T1 (FETCH) should be assigned (T2 and T3 are WAITING)
        sched_res, _ = await engine.execute(
            Command(command="SCHEDULE_QUEUE", args={"policy": "fcfs"}, idempotency_key="sq1")
        )
        assert sched_res.accepted is True
        assert engine.state.tasks[t1_id].status == TaskStatus.RUNNING
        assert engine.state.tasks[t2_id].status == TaskStatus.WAITING
        assert engine.state.tasks[t3_id].status == TaskStatus.WAITING

        # 3. Advance time by 3s to complete FETCH stage
        adv_res, adv_events = await engine.execute(
            Command(command="ADVANCE_TIME", args={"seconds": 3}, idempotency_key="adv1")
        )
        assert adv_res.accepted is True
        assert engine.state.tasks[t1_id].status == TaskStatus.DONE
        # T2 should be unblocked and QUEUED now!
        assert engine.state.tasks[t2_id].status == TaskStatus.QUEUED
        assert engine.state.tasks[t3_id].status == TaskStatus.WAITING

        # Verify UNBLOCKED and ENQUEUED events emitted
        event_types = [e.type for e in adv_events]
        assert "TASK_COMPLETED" in event_types
        assert "TASK_UNBLOCKED" in event_types
        assert "TASK_ENQUEUED" in event_types

        # 4. Schedule queue: T2 (COOK) gets assigned to W-1 and S-2 (Stove)
        await engine.execute(
            Command(command="SCHEDULE_QUEUE", args={"policy": "fcfs"}, idempotency_key="sq2")
        )
        assert engine.state.tasks[t2_id].status == TaskStatus.RUNNING
        assert engine.state.tasks[t2_id].station_id == "S-2"

        # 5. Advance time by 6s to complete COOK stage
        await engine.execute(
            Command(command="ADVANCE_TIME", args={"seconds": 6}, idempotency_key="adv2")
        )
        assert engine.state.tasks[t2_id].status == TaskStatus.DONE
        assert engine.state.tasks[t3_id].status == TaskStatus.QUEUED

        # 6. Schedule queue: T3 (SERVE) gets assigned
        await engine.execute(
            Command(command="SCHEDULE_QUEUE", args={"policy": "fcfs"}, idempotency_key="sq3")
        )
        assert engine.state.tasks[t3_id].status == TaskStatus.RUNNING

        # 7. Advance time by 2s to complete SERVE stage
        _, final_events = await engine.execute(
            Command(command="ADVANCE_TIME", args={"seconds": 2}, idempotency_key="adv3")
        )
        assert engine.state.tasks[t3_id].status == TaskStatus.DONE

        # Order should now be COMPLETED!
        order = engine.state.orders["O-0001"]
        assert order.status == OrderStatus.COMPLETED
        assert order.completed_at == 11  # 3 + 6 + 2
        order_completed_events = [e for e in final_events if e.type == "ORDER_COMPLETED"]
        assert len(order_completed_events) == 1
        payload = order_completed_events[0].payload
        assert payload["order_id"] == "O-0001"
        assert payload["duration_seconds"] == 11

    asyncio.run(scenario())


def test_cannot_manually_assign_waiting_task(tmp_path: Path) -> None:
    async def scenario() -> None:
        engine = setup_engine(tmp_path)

        await engine.execute(
            Command(command="CREATE_ORDER", args={"dish_name": "番茄湯"}, idempotency_key="o1")
        )
        order = engine.state.orders["O-0001"]
        t2_id = order.task_ids[1]  # T2 is WAITING

        # Attempt to assign waiting task directly
        cmd = Command(
            command="ASSIGN_TASK",
            args={"worker_id": "W-1", "task_id": t2_id},
            idempotency_key="assign-fail",
        )
        with pytest.raises(DomainError) as exc_info:
            await engine.execute(cmd)
        assert exc_info.value.code == "TASK_NOT_QUEUED"

    asyncio.run(scenario())


def test_api_orders_endpoint(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "core.sqlite"))

    # Initial orders should be empty
    res = client.get("/api/v1/orders")
    assert res.status_code == 200
    assert res.json()["orders"] == []

    # Create an order via command
    client.post(
        "/api/v1/commands",
        json={
            "command": "CREATE_ORDER",
            "args": {"dish_name": "炒飯", "priority": 2},
            "idempotency_key": "k-api-order-1",
        },
    )

    # Fetch orders again
    res = client.get("/api/v1/orders")
    assert res.status_code == 200
    orders = res.json()["orders"]
    assert len(orders) == 1
    assert orders[0]["dish_name"] == "炒飯"
    assert orders[0]["status"] == "in_progress"
    assert len(orders[0]["task_ids"]) == 3
