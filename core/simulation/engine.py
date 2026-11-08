"""Authoritative world engine: command validation, mutation and event emission."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from typing import Any

from core.algorithms.scheduling import ASSIGNABLE, TaskSpec, run_scheduler
from core.domain.errors import DomainError
from core.domain.models import (
    Command,
    DomainEvent,
    Order,
    OrderStatus,
    Station,
    StationStatus,
    Task,
    TaskStage,
    TaskStatus,
    Worker,
    WorkerStatus,
    WorldState,
)
from core.persistence.store import Store


@dataclass
class CommandResult:
    request_id: str
    accepted: bool
    event_ids: list[int]
    state_version: int
    error: dict[str, Any] | None = None
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "accepted": self.accepted,
            "event_ids": self.event_ids,
            "state_version": self.state_version,
            "error": self.error,
            "cached": self.cached,
        }


def _require_int(args: dict[str, Any], key: str, *, minimum: int | None = None) -> int:
    if key not in args:
        raise DomainError(
            "MISSING_ARGUMENT", f"Missing required argument: {key}", status_code=422
        )
    try:
        value = int(args[key])
    except (TypeError, ValueError) as exc:
        raise DomainError(
            "INVALID_ARGUMENT",
            f"Argument {key} must be an integer",
            status_code=422,
        ) from exc
    if minimum is not None and value < minimum:
        raise DomainError(
            "INVALID_ARGUMENT",
            f"Argument {key} must be >= {minimum}",
            status_code=422,
        )
    return value


def _event(
    state: WorldState,
    event_type: str,
    payload: dict[str, Any],
    command: Command,
    *,
    correlation_id: str | None = None,
) -> DomainEvent:
    return DomainEvent(
        type=event_type,
        sim_time=state.sim_time,
        payload=payload,
        causation_id=command.request_id or None,
        correlation_id=correlation_id,
    )


def _pick_station(state: WorldState, station_id: str | None) -> Station:
    if station_id:
        station = state.stations.get(station_id)
        if station is None:
            raise DomainError(
                "STATION_NOT_FOUND",
                f"Station {station_id} does not exist",
                status_code=404,
            )
        if station.status != StationStatus.FREE:
            raise DomainError(
                "STATION_BUSY",
                f"Station {station_id} is busy",
                status_code=409,
            )
        return station

    free = sorted(
        (s for s in state.stations.values() if s.status == StationStatus.FREE),
        key=lambda s: s.id,
    )
    if not free:
        raise DomainError(
            "NO_FREE_STATION", "No free station is available", status_code=409
        )
    return free[0]


def _assign(
    state: WorldState, task: Task, worker: Worker, station: Station, command: Command
) -> list[DomainEvent]:
    task.status = TaskStatus.RUNNING
    task.remaining_seconds = task.burst_seconds
    task.started_at = state.sim_time
    task.worker_id = worker.id
    task.station_id = station.id

    worker.status = WorkerStatus.BUSY
    worker.task_id = task.id
    station.status = StationStatus.BUSY
    station.task_id = task.id

    return [
        _event(
            state,
            "WORKER_ASSIGNED",
            {
                "worker_id": worker.id,
                "task_id": task.id,
                "station_id": station.id,
            },
            command,
            correlation_id=task.id,
        ),
        _event(
            state,
            "TASK_STARTED",
            {
                "task_id": task.id,
                "worker_id": worker.id,
                "station_id": station.id,
                "started_at": state.sim_time,
                "finish_at": state.sim_time + task.burst_seconds,
            },
            command,
            correlation_id=task.id,
        ),
    ]


def _handle_enqueue_task(
    state: WorldState, args: dict[str, Any], command: Command
) -> list[DomainEvent]:
    burst = _require_int(args, "burst_seconds", minimum=1)
    priority = int(args.get("priority", 0))
    name = str(args.get("name") or f"Task {state.next_task_seq}")

    task_id = f"T-{state.next_task_seq:04d}"
    state.next_task_seq += 1
    task = Task(
        id=task_id,
        name=name,
        burst_seconds=burst,
        priority=priority,
        enqueued_at=state.sim_time,
    )
    state.tasks[task_id] = task
    return [
        _event(
            state,
            "TASK_ENQUEUED",
            {"task": task.to_dict()},
            command,
            correlation_id=task_id,
        )
    ]


DISH_RECIPES: dict[str, list[dict[str, Any]]] = {
    "番茄湯": [
        {"stage": TaskStage.FETCH, "name": "番茄湯-取料", "burst_seconds": 3, "preferred_station_id": "S-1"},
        {"stage": TaskStage.COOK, "name": "番茄湯-烹調", "burst_seconds": 6, "preferred_station_id": "S-2"},
        {"stage": TaskStage.SERVE, "name": "番茄湯-送餐", "burst_seconds": 2, "preferred_station_id": None},
    ],
    "炒飯": [
        {"stage": TaskStage.FETCH, "name": "炒飯-取料", "burst_seconds": 2, "preferred_station_id": "S-1"},
        {"stage": TaskStage.COOK, "name": "炒飯-烹調", "burst_seconds": 8, "preferred_station_id": "S-2"},
        {"stage": TaskStage.SERVE, "name": "炒飯-送餐", "burst_seconds": 2, "preferred_station_id": None},
    ],
}


def _handle_create_order(
    state: WorldState, args: dict[str, Any], command: Command
) -> list[DomainEvent]:
    dish_name = str(args.get("dish_name") or "").strip()
    if not dish_name:
        raise DomainError(
            "MISSING_ARGUMENT", "Missing required argument: dish_name", status_code=422
        )
    priority = int(args.get("priority", 0))

    stages_config = args.get("stages")
    if not stages_config:
        stages_config = DISH_RECIPES.get(
            dish_name,
            [
                {"stage": TaskStage.FETCH, "name": f"{dish_name}-取料", "burst_seconds": 3, "preferred_station_id": "S-1"},
                {"stage": TaskStage.COOK, "name": f"{dish_name}-烹調", "burst_seconds": 5, "preferred_station_id": "S-2"},
                {"stage": TaskStage.SERVE, "name": f"{dish_name}-送餐", "burst_seconds": 2, "preferred_station_id": None},
            ],
        )

    order_id = f"O-{state.next_order_seq:04d}"
    state.next_order_seq += 1

    task_ids: list[str] = []
    prev_task_id: str | None = None
    first_task: Task | None = None

    for idx, stage_info in enumerate(stages_config):
        burst = int(stage_info.get("burst_seconds", 3))
        stage_name = str(stage_info.get("stage", TaskStage.FETCH))
        name = str(stage_info.get("name") or f"{dish_name}-{stage_name}")
        pref_station = stage_info.get("preferred_station_id")

        task_id = f"T-{state.next_task_seq:04d}"
        state.next_task_seq += 1
        task_ids.append(task_id)

        is_first = (idx == 0)
        task = Task(
            id=task_id,
            name=name,
            burst_seconds=burst,
            priority=priority,
            status=TaskStatus.QUEUED if is_first else TaskStatus.WAITING,
            enqueued_at=state.sim_time if is_first else 0,
            order_id=order_id,
            stage=stage_name,
            prerequisite_task_id=prev_task_id,
            preferred_station_id=pref_station,
        )
        state.tasks[task_id] = task
        if is_first:
            first_task = task
        prev_task_id = task_id

    order = Order(
        id=order_id,
        dish_name=dish_name,
        status=OrderStatus.IN_PROGRESS,
        task_ids=task_ids,
        created_at=state.sim_time,
        priority=priority,
    )
    state.orders[order_id] = order

    events: list[DomainEvent] = [
        _event(
            state,
            "ORDER_CREATED",
            {"order": order.to_dict()},
            command,
            correlation_id=order_id,
        )
    ]
    if first_task:
        events.append(
            _event(
                state,
                "TASK_ENQUEUED",
                {"task": first_task.to_dict()},
                command,
                correlation_id=order_id,
            )
        )
    return events


def _handle_assign_task(
    state: WorldState, args: dict[str, Any], command: Command
) -> list[DomainEvent]:
    worker_id = str(args.get("worker_id", ""))
    task_id = str(args.get("task_id", ""))
    worker = state.workers.get(worker_id)
    if worker is None:
        raise DomainError(
            "WORKER_NOT_FOUND", f"Worker {worker_id} does not exist", status_code=404
        )
    if worker.status != WorkerStatus.IDLE:
        raise DomainError(
            "WORKER_BUSY", f"Worker {worker_id} is busy", status_code=409
        )

    task = state.tasks.get(task_id)
    if task is None:
        raise DomainError(
            "TASK_NOT_FOUND", f"Task {task_id} does not exist", status_code=404
        )
    if task.status != TaskStatus.QUEUED:
        raise DomainError(
            "TASK_NOT_QUEUED",
            f"Task {task_id} is not queued (status={task.status})",
            status_code=409,
        )

    station = _pick_station(state, args.get("station_id"))
    return _assign(state, task, worker, station, command)


def _handle_schedule_queue(
    state: WorldState, args: dict[str, Any], command: Command
) -> list[DomainEvent]:
    policy = str(args.get("policy", state.policy)).strip().lower()
    if policy not in ASSIGNABLE:
        raise DomainError(
            "POLICY_NOT_ASSIGNABLE",
            f"Policy {policy} cannot drive non-preemptive world assignment",
            status_code=422,
            details={"assignable": sorted(ASSIGNABLE)},
        )

    queued = sorted(
        (t for t in state.tasks.values() if t.status == TaskStatus.QUEUED),
        key=lambda t: (t.enqueued_at, t.id),
    )
    state.policy = policy
    if not queued:
        return [
            _event(
                state,
                "QUEUE_SCHEDULED",
                {"policy": policy, "assigned": 0, "order": []},
                command,
            )
        ]

    specs = [
        TaskSpec(
            id=task.id,
            arrival=task.enqueued_at,
            burst=task.burst_seconds,
            priority=task.priority,
        )
        for task in queued
    ]
    plan = run_scheduler(policy, specs)

    idle_workers = sorted(
        (w for w in state.workers.values() if w.status == WorkerStatus.IDLE),
        key=lambda w: w.id,
    )
    free_stations = sorted(
        (s for s in state.stations.values() if s.status == StationStatus.FREE),
        key=lambda s: s.id,
    )

    assign_events: list[DomainEvent] = []
    assigned: list[str] = []
    for task_id in plan.order:
        if not idle_workers or not free_stations:
            break
        task = state.tasks[task_id]
        chosen_station: Station | None = None
        if task.preferred_station_id:
            for s in free_stations:
                if s.id == task.preferred_station_id:
                    chosen_station = s
                    break
        if chosen_station is None:
            chosen_station = free_stations[0]

        free_stations.remove(chosen_station)
        worker = idle_workers.pop(0)
        assign_events.extend(_assign(state, task, worker, chosen_station, command))
        assigned.append(task_id)

    summary = _event(
        state,
        "QUEUE_SCHEDULED",
        {
            "policy": policy,
            "assigned": len(assigned),
            "order": assigned,
            "metrics": plan.metrics,
        },
        command,
    )
    return [summary, *assign_events]


def _complete_task(state: WorldState, task: Task, command: Command) -> list[DomainEvent]:
    task.status = TaskStatus.DONE
    task.remaining_seconds = 0
    task.finished_at = state.sim_time

    if task.worker_id and (worker := state.workers.get(task.worker_id)):
        worker.status = WorkerStatus.IDLE
        worker.task_id = None
    if task.station_id and (station := state.stations.get(task.station_id)):
        station.status = StationStatus.FREE
        station.task_id = None

    events = [
        _event(
            state,
            "TASK_COMPLETED",
            {
                "task_id": task.id,
                "worker_id": task.worker_id,
                "station_id": task.station_id,
                "finished_at": state.sim_time,
            },
            command,
            correlation_id=task.order_id or task.id,
        )
    ]

    # Check for dependent tasks waiting on this completed task
    for next_task in state.tasks.values():
        if next_task.prerequisite_task_id == task.id and next_task.status == TaskStatus.WAITING:
            next_task.status = TaskStatus.QUEUED
            next_task.enqueued_at = state.sim_time
            events.append(
                _event(
                    state,
                    "TASK_UNBLOCKED",
                    {
                        "task_id": next_task.id,
                        "prerequisite_task_id": task.id,
                        "order_id": next_task.order_id,
                        "stage": next_task.stage,
                    },
                    command,
                    correlation_id=next_task.order_id or next_task.id,
                )
            )
            events.append(
                _event(
                    state,
                    "TASK_ENQUEUED",
                    {"task": next_task.to_dict()},
                    command,
                    correlation_id=next_task.order_id or next_task.id,
                )
            )

    # If this task belongs to an order, check if all tasks of the order are finished
    if task.order_id and (order := state.orders.get(task.order_id)):
        order_tasks = [state.tasks[tid] for tid in order.task_ids if tid in state.tasks]
        if order_tasks and all(t.status == TaskStatus.DONE for t in order_tasks):
            order.status = OrderStatus.COMPLETED
            order.completed_at = state.sim_time
            duration = (order.completed_at - order.created_at) if order.completed_at is not None else 0
            events.append(
                _event(
                    state,
                    "ORDER_COMPLETED",
                    {
                        "order_id": order.id,
                        "dish_name": order.dish_name,
                        "created_at": order.created_at,
                        "completed_at": order.completed_at,
                        "duration_seconds": duration,
                    },
                    command,
                    correlation_id=order.id,
                )
            )

    return events


def _handle_advance_time(
    state: WorldState, args: dict[str, Any], command: Command
) -> list[DomainEvent]:
    seconds = _require_int(args, "seconds", minimum=1)
    start = state.sim_time
    target = start + seconds
    events: list[DomainEvent] = []

    while True:
        running = [
            task for task in state.tasks.values() if task.status == TaskStatus.RUNNING
        ]
        if not running:
            break
        finish_at = min(
            (task.started_at or 0) + task.burst_seconds for task in running
        )
        if finish_at > target:
            break

        state.sim_time = finish_at
        due = sorted(
            (
                task
                for task in running
                if (task.started_at or 0) + task.burst_seconds == finish_at
            ),
            key=lambda task: task.id,
        )
        for task in due:
            events.extend(_complete_task(state, task, command))

    state.sim_time = target
    events.append(
        _event(
            state,
            "TIME_ADVANCED",
            {"from": start, "to": target, "seconds": seconds},
            command,
        )
    )
    return events


def _handle_set_policy(
    state: WorldState, args: dict[str, Any], command: Command
) -> list[DomainEvent]:
    policy = str(args.get("policy", "")).strip().lower()
    if policy not in ASSIGNABLE:
        raise DomainError(
            "POLICY_NOT_ASSIGNABLE",
            f"Policy {policy} cannot drive non-preemptive world assignment",
            status_code=422,
            details={"assignable": sorted(ASSIGNABLE)},
        )
    state.policy = policy
    return [_event(state, "POLICY_CHANGED", {"policy": policy}, command)]


_HANDLERS = {
    "ENQUEUE_TASK": _handle_enqueue_task,
    "CREATE_ORDER": _handle_create_order,
    "ASSIGN_TASK": _handle_assign_task,
    "SCHEDULE_QUEUE": _handle_schedule_queue,
    "ADVANCE_TIME": _handle_advance_time,
    "SET_POLICY": _handle_set_policy,
}


def apply_command(state: WorldState, command: Command) -> list[DomainEvent]:
    """Apply one command to a working copy of the state and return events.

    Raises DomainError before any commit when validation fails.
    """
    name = command.command.strip().upper()
    handler = _HANDLERS.get(name)
    if handler is None:
        raise DomainError(
            "UNKNOWN_COMMAND",
            f"Unknown command: {command.command}",
            status_code=422,
            details={"known": sorted(_HANDLERS)},
        )
    return handler(state, command.args, command)


class WorldEngine:
    """Single-writer command pipeline over an authoritative WorldState."""

    def __init__(self, state: WorldState, store: Store) -> None:
        self.state = state
        self.store = store
        self._lock = asyncio.Lock()

    async def execute(self, command: Command) -> tuple[CommandResult, list[DomainEvent]]:
        async with self._lock:
            cached = self.store.get_idempotent(command.idempotency_key)
            if cached is not None:
                return (
                    CommandResult(
                        request_id=str(cached.get("request_id", command.request_id)),
                        accepted=bool(cached.get("accepted", True)),
                        event_ids=list(cached.get("event_ids", [])),
                        state_version=int(cached.get("state_version", self.state.version)),
                        error=cached.get("error"),
                        cached=True,
                    ),
                    [],
                )

            working = copy.deepcopy(self.state)
            working.version += 1
            events = apply_command(working, command)

            for event in events:
                event.state_version = working.version

            response = {
                "request_id": command.request_id,
                "accepted": True,
                "event_ids": [],
                "state_version": working.version,
                "error": None,
            }
            event_ids = self.store.commit(
                working, events, command.idempotency_key, response
            )
            for event, event_id in zip(events, event_ids):
                event.event_id = event_id
            self.state = working
            return (
                CommandResult(
                    request_id=command.request_id,
                    accepted=True,
                    event_ids=event_ids,
                    state_version=working.version,
                ),
                events,
            )

    def restore(self, state: WorldState) -> None:
        """Replace the authoritative state with a restored save (`08-04`).

        Restoring does not re-settle past events: the save already holds the
        settled result, so nothing here may emit or replay domain events.
        """
        self.state = state

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state.to_dict(),
            "last_event_id": self.state.last_event_id,
            "state_version": self.state.version,
        }
