"""World entities and the authoritative state container.

These objects are plain Python on purpose: the domain layer must not depend on
FastAPI, SQLite, NumPy or Numba.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class TaskStage(StrEnum):
    FETCH = "FETCH"   # 取放食材 (docs/11-01 §3.2)
    COOK = "COOK"     # 烹飪 (docs/11-01 §3.3)
    SERVE = "SERVE"   # 送餐 (docs/11-01 §3.4)


class TaskStatus(StrEnum):
    QUEUED = "queued"
    WAITING = "waiting"   # 等待前置階段完成 (docs/11-01 §4.3)
    RUNNING = "running"
    DONE = "done"


class OrderStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkerStatus(StrEnum):
    IDLE = "idle"
    BUSY = "busy"


class StationStatus(StrEnum):
    FREE = "free"
    BUSY = "busy"


@dataclass
class Task:
    id: str
    name: str
    burst_seconds: int
    priority: int = 0
    status: str = TaskStatus.QUEUED
    remaining_seconds: int | None = None
    enqueued_at: int = 0
    started_at: int | None = None
    finished_at: int | None = None
    worker_id: str | None = None
    station_id: str | None = None
    order_id: str | None = None
    stage: str | None = None
    prerequisite_task_id: str | None = None
    preferred_station_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # StrEnum serializes as its value; normalize for older JSON encoders.
        data["status"] = str(self.status)
        return data


@dataclass
class Order:
    id: str
    dish_name: str
    status: str = OrderStatus.PENDING
    task_ids: list[str] = field(default_factory=list)
    created_at: int = 0
    completed_at: int | None = None
    priority: int = 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = str(self.status)
        return data


@dataclass
class Worker:
    id: str
    name: str
    status: str = WorkerStatus.IDLE
    task_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = str(self.status)
        return data


@dataclass
class Station:
    id: str
    name: str
    status: str = StationStatus.FREE
    task_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = str(self.status)
        return data


@dataclass
class WorldState:
    """The single authoritative world snapshot held by CORE."""

    sim_time: int = 0
    version: int = 0
    seed: int = 42
    policy: str = "fcfs"
    next_task_seq: int = 1
    next_order_seq: int = 1
    last_event_id: int = 0
    tasks: dict[str, Task] = field(default_factory=dict)
    workers: dict[str, Worker] = field(default_factory=dict)
    stations: dict[str, Station] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)

    @classmethod
    def new(cls, *, seed: int = 42) -> "WorldState":
        """Create the minimal M1/M2 world: two workers and two work stations.

        Restaurant-specific entities (orders, inventory, nutrition) are added
        progressively; this skeleton exercises commands, scheduling, chained
        tasks and deterministic time advance.
        """
        return cls(
            seed=seed,
            workers={
                "W-1": Worker(id="W-1", name="Worker 1"),
                "W-2": Worker(id="W-2", name="Worker 2"),
            },
            stations={
                "S-1": Station(id="S-1", name="Prep Station"),
                "S-2": Station(id="S-2", name="Stove"),
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sim_time": self.sim_time,
            "version": self.version,
            "seed": self.seed,
            "policy": self.policy,
            "next_task_seq": self.next_task_seq,
            "next_order_seq": self.next_order_seq,
            "last_event_id": self.last_event_id,
            "tasks": {key: task.to_dict() for key, task in self.tasks.items()},
            "workers": {key: worker.to_dict() for key, worker in self.workers.items()},
            "stations": {
                key: station.to_dict() for key, station in self.stations.items()
            },
            "orders": {key: order.to_dict() for key, order in self.orders.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldState":
        state = cls(
            sim_time=int(data.get("sim_time", 0)),
            version=int(data.get("version", 0)),
            seed=int(data.get("seed", 42)),
            policy=str(data.get("policy", "fcfs")),
            next_task_seq=int(data.get("next_task_seq", 1)),
            next_order_seq=int(data.get("next_order_seq", 1)),
            last_event_id=int(data.get("last_event_id", 0)),
        )
        for key, raw in data.get("tasks", {}).items():
            state.tasks[key] = Task(**raw)
        for key, raw in data.get("workers", {}).items():
            state.workers[key] = Worker(**raw)
        for key, raw in data.get("stations", {}).items():
            state.stations[key] = Station(**raw)
        for key, raw in data.get("orders", {}).items():
            state.orders[key] = Order(**raw)
        return state
        return state


@dataclass
class Command:
    command: str
    args: dict[str, Any]
    idempotency_key: str
    client: str = "unknown"
    request_id: str = ""


@dataclass
class DomainEvent:
    type: str
    sim_time: int
    payload: dict[str, Any]
    state_version: int = 0
    causation_id: str | None = None
    correlation_id: str | None = None
    event_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "sim_time": self.sim_time,
            "state_version": self.state_version,
            "payload": self.payload,
            "causation_id": self.causation_id,
            "correlation_id": self.correlation_id,
        }
