"""Reference OS scheduling algorithms.

Pure functions only: no DB, FastAPI, NumPy or Numba. These are the readable
reference implementations required by the course; optimized Numba kernels can
be added later and must match these results on fixed workloads.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class TaskSpec:
    id: str
    arrival: int
    burst: int
    priority: int = 0

    def __post_init__(self) -> None:
        if self.arrival < 0:
            raise ValueError("arrival must be >= 0")
        if self.burst <= 0:
            raise ValueError("burst must be > 0")


@dataclass(frozen=True)
class GanttSlice:
    task_id: str
    start: int
    end: int


@dataclass(frozen=True)
class TraceStep:
    step: int
    skill: str
    algorithm: str
    package: str
    input: dict[str, Any]
    output: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "skill": self.skill,
            "algorithm": self.algorithm,
            "package": self.package,
            "input": self.input,
            "output": self.output,
        }


@dataclass
class ScheduleResult:
    algorithm: str
    order: list[str]
    completion_order: list[str]
    start: dict[str, int]
    finish: dict[str, int]
    waiting: dict[str, int]
    turnaround: dict[str, int]
    timeline: list[GanttSlice]
    trace: list[TraceStep]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "order": self.order,
            "completion_order": self.completion_order,
            "start": self.start,
            "finish": self.finish,
            "waiting": self.waiting,
            "turnaround": self.turnaround,
            "timeline": [
                {"task_id": s.task_id, "start": s.start, "end": s.end}
                for s in self.timeline
            ],
            "trace": [step.to_dict() for step in self.trace],
            "metrics": self.metrics,
        }


def _add_trace(
    trace: list[TraceStep],
    algorithm: str,
    time: int,
    ready: Iterable[str],
    selected: str,
    extra: dict[str, Any] | None = None,
) -> None:
    output: dict[str, Any] = {"selected": selected}
    if extra:
        output.update(extra)
    trace.append(
        TraceStep(
            step=len(trace) + 1,
            skill="schedule_tasks",
            algorithm=algorithm,
            package="core.algorithms.scheduling",
            input={"time": time, "ready": list(ready)},
            output=output,
        )
    )


def _finalize(
    algorithm: str,
    specs: list[TaskSpec],
    timeline: list[GanttSlice],
    trace: list[TraceStep],
) -> ScheduleResult:
    by_id = {spec.id: spec for spec in specs}
    first_start: dict[str, int] = {}
    finish: dict[str, int] = {}
    for slice_ in sorted(timeline, key=lambda s: (s.start, s.end, s.task_id)):
        first_start.setdefault(slice_.task_id, slice_.start)
        finish[slice_.task_id] = max(finish.get(slice_.task_id, 0), slice_.end)

    order = sorted(first_start, key=lambda tid: (first_start[tid], finish[tid], tid))
    completion_order = sorted(
        finish, key=lambda tid: (finish[tid], first_start[tid], tid)
    )
    waiting = {
        tid: max(0, finish[tid] - by_id[tid].arrival - by_id[tid].burst)
        for tid in finish
    }
    turnaround = {tid: finish[tid] - by_id[tid].arrival for tid in finish}
    makespan = max(finish.values(), default=0)
    total_burst = sum(spec.burst for spec in specs)
    completed = len(finish)

    metrics = {
        "makespan": float(makespan),
        "avg_waiting": (sum(waiting.values()) / completed) if completed else 0.0,
        "avg_turnaround": (sum(turnaround.values()) / completed) if completed else 0.0,
        "throughput": (completed / makespan) if makespan else 0.0,
        "cpu_utilization": (total_burst / makespan) if makespan else 0.0,
    }
    return ScheduleResult(
        algorithm=algorithm,
        order=order,
        completion_order=completion_order,
        start=first_start,
        finish=finish,
        waiting=waiting,
        turnaround=turnaround,
        timeline=timeline,
        trace=trace,
        metrics=metrics,
    )


def fcfs(specs: Iterable[TaskSpec]) -> ScheduleResult:
    """First Come First Served, non-preemptive."""
    specs = list(specs)
    timeline: list[GanttSlice] = []
    trace: list[TraceStep] = []
    now = 0
    for spec in sorted(specs, key=lambda s: (s.arrival, s.id)):
        start = max(now, spec.arrival)
        end = start + spec.burst
        _add_trace(trace, "FCFS", start, [spec.id], spec.id)
        timeline.append(GanttSlice(spec.id, start, end))
        now = end
    return _finalize("FCFS", specs, timeline, trace)


def sjf(specs: Iterable[TaskSpec]) -> ScheduleResult:
    """Shortest Job First, non-preemptive. Gaps are skipped deterministically."""
    specs = list(specs)
    timeline: list[GanttSlice] = []
    trace: list[TraceStep] = []
    done: set[str] = set()
    now = min((spec.arrival for spec in specs), default=0)

    while len(done) < len(specs):
        available = [spec for spec in specs if spec.arrival <= now and spec.id not in done]
        if not available:
            now = min(spec.arrival for spec in specs if spec.id not in done)
            continue
        spec = min(available, key=lambda s: (s.burst, s.arrival, s.id))
        _add_trace(trace, "SJF", now, (s.id for s in available), spec.id)
        timeline.append(GanttSlice(spec.id, now, now + spec.burst))
        now += spec.burst
        done.add(spec.id)

    return _finalize("SJF", specs, timeline, trace)


def srtf(specs: Iterable[TaskSpec]) -> ScheduleResult:
    """Shortest Remaining Time First, preemptive."""
    specs = list(specs)
    if not specs:
        return _finalize("SRTF", specs, [], [])

    remaining = {spec.id: spec.burst for spec in specs}
    timeline: list[GanttSlice] = []
    trace: list[TraceStep] = []
    now = min(spec.arrival for spec in specs)
    last_pick: str | None = None

    while any(value > 0 for value in remaining.values()):
        available = [
            spec for spec in specs if spec.arrival <= now and remaining[spec.id] > 0
        ]
        if not available:
            now = min(spec.arrival for spec in specs if remaining[spec.id] > 0)
            last_pick = None
            continue

        spec = min(available, key=lambda s: (remaining[s.id], s.arrival, s.id))
        if spec.id != last_pick:
            _add_trace(
                trace,
                "SRTF",
                now,
                (s.id for s in available),
                spec.id,
                {"remaining": remaining[spec.id]},
            )
            last_pick = spec.id

        next_arrival = min(
            (s.arrival for s in specs if s.arrival > now and remaining[s.id] > 0),
            default=None,
        )
        run_until = now + remaining[spec.id]
        if next_arrival is not None and next_arrival < run_until:
            run_until = next_arrival

        duration = run_until - now
        if duration <= 0:  # defensive: never loop forever on malformed input
            raise ValueError("scheduler made no progress")
        timeline.append(GanttSlice(spec.id, now, run_until))
        remaining[spec.id] -= duration
        now = run_until

    return _finalize("SRTF", specs, timeline, trace)


def priority_aging(
    specs: Iterable[TaskSpec], *, aging_interval: int = 5
) -> ScheduleResult:
    """Priority scheduling with aging, non-preemptive.

    Higher `priority` value means more important. A task gains one effective
    priority point for every full `aging_interval` it waits.
    """
    if aging_interval <= 0:
        raise ValueError("aging_interval must be > 0")
    specs = list(specs)
    timeline: list[GanttSlice] = []
    trace: list[TraceStep] = []
    done: set[str] = set()
    now = min((spec.arrival for spec in specs), default=0)

    while len(done) < len(specs):
        available = [spec for spec in specs if spec.arrival <= now and spec.id not in done]
        if not available:
            now = min(spec.arrival for spec in specs if spec.id not in done)
            continue

        def effective(spec: TaskSpec) -> int:
            return spec.priority + (now - spec.arrival) // aging_interval

        spec = min(available, key=lambda s: (-effective(s), s.arrival, s.id))
        _add_trace(
            trace,
            "Priority+Aging",
            now,
            (s.id for s in available),
            spec.id,
            {"effective_priority": effective(spec)},
        )
        timeline.append(GanttSlice(spec.id, now, now + spec.burst))
        now += spec.burst
        done.add(spec.id)

    return _finalize("Priority+Aging", specs, timeline, trace)


def round_robin(specs: Iterable[TaskSpec], *, quantum: int = 2) -> ScheduleResult:
    """Round Robin with a fixed time quantum."""
    if quantum <= 0:
        raise ValueError("quantum must be > 0")
    specs = list(specs)
    if not specs:
        return _finalize("RR", specs, [], [])

    pending = sorted(specs, key=lambda s: (s.arrival, s.id))
    remaining = {spec.id: spec.burst for spec in specs}
    timeline: list[GanttSlice] = []
    trace: list[TraceStep] = []
    ready: deque[TaskSpec] = deque()
    index = 0
    now = pending[0].arrival

    while ready or index < len(pending):
        while index < len(pending) and pending[index].arrival <= now:
            ready.append(pending[index])
            index += 1
        if not ready:
            now = pending[index].arrival
            continue

        spec = ready.popleft()
        duration = min(quantum, remaining[spec.id])
        _add_trace(
            trace,
            "RR",
            now,
            (s.id for s in ready),
            spec.id,
            {"quantum": quantum, "remaining": remaining[spec.id]},
        )
        timeline.append(GanttSlice(spec.id, now, now + duration))
        remaining[spec.id] -= duration
        now += duration

        while index < len(pending) and pending[index].arrival <= now:
            ready.append(pending[index])
            index += 1
        if remaining[spec.id] > 0:
            ready.append(spec)

    return _finalize("RR", specs, timeline, trace)


SCHEDULERS: dict[str, Callable[..., ScheduleResult]] = {
    "fcfs": fcfs,
    "sjf": sjf,
    "srtf": srtf,
    "priority_aging": priority_aging,
    "rr": round_robin,
}

# Policies that can drive the non-preemptive M1 world assignment.
ASSIGNABLE: dict[str, Callable[..., ScheduleResult]] = {
    "fcfs": fcfs,
    "sjf": sjf,
    "priority_aging": priority_aging,
}

ALGORITHM_INFO: list[dict[str, Any]] = [
    {"name": "fcfs", "label": "FCFS", "assignable": True},
    {"name": "sjf", "label": "SJF", "assignable": True},
    {"name": "priority_aging", "label": "Priority+Aging", "assignable": True},
    {"name": "srtf", "label": "SRTF", "assignable": False},
    {"name": "rr", "label": "Round Robin", "assignable": False},
]


def run_scheduler(name: str, specs: Iterable[TaskSpec], **kwargs: Any) -> ScheduleResult:
    key = name.strip().lower()
    try:
        scheduler = SCHEDULERS[key]
    except KeyError as exc:
        raise ValueError(f"unknown scheduler: {name}") from exc
    return scheduler(specs, **kwargs)
