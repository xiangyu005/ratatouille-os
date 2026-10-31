"""World command/event tests: correctness, idempotency, determinism, reload."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from core.domain.errors import DomainError
from core.domain.models import Command, WorldState
from core.persistence.store import Store
from core.simulation.engine import WorldEngine


def make_engine(path: Path) -> WorldEngine:
    store = Store(path)
    raw_state = store.load_latest_state()
    state = WorldState.from_dict(raw_state) if raw_state else WorldState.new(seed=42)
    return WorldEngine(state, store)


def command(
    name: str,
    args: dict | None = None,
    key: str | None = None,
    request_id: str = "req-test",
) -> Command:
    return Command(
        command=name,
        args=args or {},
        idempotency_key=key or f"{name}-{request_id}",
        request_id=request_id,
    )


def test_enqueue_schedule_advance_completes_tasks(tmp_path: Path) -> None:
    engine = make_engine(tmp_path / "core.sqlite")

    async def scenario() -> None:
        await engine.execute(
            command(
                "ENQUEUE_TASK",
                {"name": "Soup", "burst_seconds": 4, "priority": 0},
                "k1",
                "r1",
            )
        )
        await engine.execute(
            command(
                "ENQUEUE_TASK",
                {"name": "Salad", "burst_seconds": 2, "priority": 5},
                "k2",
                "r2",
            )
        )
        result, events = await engine.execute(
            command("SCHEDULE_QUEUE", {"policy": "sjf"}, "k3", "r3")
        )

        assert result.accepted
        assert [event.type for event in events][0] == "QUEUE_SCHEDULED"
        assert sum(1 for event in events if event.type == "TASK_STARTED") == 2
        # SJF picks the 2s task first; W-1 / S-1 get it.
        assert engine.state.tasks["T-0002"].worker_id == "W-1"
        assert engine.state.tasks["T-0001"].worker_id == "W-2"

        await engine.execute(command("ADVANCE_TIME", {"seconds": 2}, "k4", "r4"))
        assert engine.state.sim_time == 2
        assert engine.state.tasks["T-0002"].status == "done"
        assert engine.state.tasks["T-0001"].status == "running"

        await engine.execute(command("ADVANCE_TIME", {"seconds": 2}, "k5", "r5"))
        assert engine.state.sim_time == 4
        assert all(task.status == "done" for task in engine.state.tasks.values())
        assert all(worker.status == "idle" for worker in engine.state.workers.values())
        assert all(
            station.status == "free" for station in engine.state.stations.values()
        )

    asyncio.run(scenario())


def test_idempotent_command_is_applied_once(tmp_path: Path) -> None:
    engine = make_engine(tmp_path / "core.sqlite")

    async def scenario() -> None:
        first, first_events = await engine.execute(
            command("ENQUEUE_TASK", {"burst_seconds": 1}, "same-key", "r1")
        )
        second, second_events = await engine.execute(
            command("ENQUEUE_TASK", {"burst_seconds": 1}, "same-key", "r2")
        )

        assert first.accepted and not first.cached
        assert second.accepted and second.cached
        assert second_events == []
        assert len(engine.state.tasks) == 1
        assert first.event_ids == second.event_ids

    asyncio.run(scenario())


def test_rejected_command_does_not_commit(tmp_path: Path) -> None:
    engine = make_engine(tmp_path / "core.sqlite")

    async def scenario() -> None:
        await engine.execute(
            command("ENQUEUE_TASK", {"burst_seconds": 2}, "k1", "r1")
        )
        await engine.execute(
            command("ENQUEUE_TASK", {"burst_seconds": 2}, "k2", "r2")
        )
        await engine.execute(
            command("ASSIGN_TASK", {"worker_id": "W-1", "task_id": "T-0001"}, "k3", "r3")
        )
        before = engine.state.version

        with pytest.raises(DomainError) as excinfo:
            await engine.execute(
                command(
                    "ASSIGN_TASK",
                    {"worker_id": "W-1", "task_id": "T-0002"},
                    "k4",
                    "r4",
                )
            )

        assert excinfo.value.code == "WORKER_BUSY"
        assert engine.state.version == before
        assert len(engine.store.get_events()) == 4

    asyncio.run(scenario())


def test_unknown_command_and_invalid_policy(tmp_path: Path) -> None:
    engine = make_engine(tmp_path / "core.sqlite")

    async def scenario() -> None:
        with pytest.raises(DomainError) as unknown:
            await engine.execute(command("NOT_A_COMMAND", {}, "k1", "r1"))
        assert unknown.value.code == "UNKNOWN_COMMAND"

        with pytest.raises(DomainError) as policy:
            await engine.execute(
                command("SET_POLICY", {"policy": "srtf"}, "k2", "r2")
            )
        assert policy.value.code == "POLICY_NOT_ASSIGNABLE"

    asyncio.run(scenario())


def test_same_commands_produce_same_event_sequence(tmp_path: Path) -> None:
    def run(path: Path) -> list[dict]:
        engine = make_engine(path)
        commands = [
            command("ENQUEUE_TASK", {"burst_seconds": 3}, "a", "r1"),
            command("ENQUEUE_TASK", {"burst_seconds": 1}, "b", "r2"),
            command("SCHEDULE_QUEUE", {"policy": "sjf"}, "c", "r3"),
            command("ADVANCE_TIME", {"seconds": 1}, "d", "r4"),
            command("ADVANCE_TIME", {"seconds": 2}, "e", "r5"),
        ]

        async def scenario() -> None:
            for item in commands:
                await engine.execute(item)

        asyncio.run(scenario())
        return [
            {
                "type": event["type"],
                "sim_time": event["sim_time"],
                "payload": event["payload"],
            }
            for event in engine.store.get_events()
        ]

    first = run(tmp_path / "a.sqlite")
    second = run(tmp_path / "b.sqlite")
    assert first == second


def test_state_reloads_from_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "core.sqlite"

    async def scenario() -> None:
        engine = make_engine(path)
        await engine.execute(
            command("ENQUEUE_TASK", {"name": "Reload", "burst_seconds": 2}, "k1", "r1")
        )
        assert engine.state.tasks["T-0001"].name == "Reload"

    asyncio.run(scenario())

    reloaded = make_engine(path)
    assert reloaded.state.tasks["T-0001"].name == "Reload"
    assert reloaded.state.version == 1
