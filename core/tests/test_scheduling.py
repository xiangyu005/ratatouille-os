"""Fixed-workload tests for the reference scheduling algorithms."""

from __future__ import annotations

import pytest

from core.algorithms.scheduling import (
    TaskSpec,
    fcfs,
    priority_aging,
    round_robin,
    run_scheduler,
    sjf,
    srtf,
)


def test_fcfs_known_workload() -> None:
    specs = [TaskSpec("A", 0, 5), TaskSpec("B", 1, 3), TaskSpec("C", 2, 1)]
    result = fcfs(specs)

    assert result.order == ["A", "B", "C"]
    assert result.completion_order == ["A", "B", "C"]
    assert result.finish == {"A": 5, "B": 8, "C": 9}
    assert result.waiting == {"A": 0, "B": 4, "C": 6}
    assert result.metrics["makespan"] == 9.0
    assert result.metrics["avg_waiting"] == pytest.approx(10 / 3)


def test_sjf_known_workload() -> None:
    specs = [TaskSpec("A", 0, 5), TaskSpec("B", 1, 3), TaskSpec("C", 2, 1)]
    result = sjf(specs)

    assert result.order == ["A", "C", "B"]
    assert result.completion_order == ["A", "C", "B"]
    assert result.finish == {"A": 5, "C": 6, "B": 9}
    assert result.waiting == {"A": 0, "C": 3, "B": 5}


def test_sjf_skips_idle_gap() -> None:
    specs = [TaskSpec("D", 5, 2), TaskSpec("E", 0, 1)]
    result = sjf(specs)

    assert result.order == ["E", "D"]
    assert result.finish == {"E": 1, "D": 7}
    assert result.metrics["makespan"] == 7.0


def test_srtf_preempts_known_workload() -> None:
    specs = [TaskSpec("A", 0, 5), TaskSpec("B", 1, 3), TaskSpec("C", 2, 1)]
    result = srtf(specs)

    assert result.order == ["A", "B", "C"]  # dispatch order
    assert result.completion_order == ["C", "B", "A"]
    assert result.finish == {"A": 9, "B": 5, "C": 3}
    assert result.waiting == {"A": 4, "B": 1, "C": 0}
    assert [(s.task_id, s.start, s.end) for s in result.timeline] == [
        ("A", 0, 1),
        ("B", 1, 2),
        ("C", 2, 3),
        ("B", 3, 5),
        ("A", 5, 9),
    ]


def test_priority_aging_changes_order() -> None:
    specs = [
        TaskSpec("A", 0, 2, 1),
        TaskSpec("B", 0, 2, 3),
        TaskSpec("C", 0, 2, 2),
    ]
    result = priority_aging(specs, aging_interval=2)

    assert result.order == ["B", "C", "A"]
    assert result.finish == {"A": 6, "B": 2, "C": 4}
    assert result.waiting == {"A": 4, "B": 0, "C": 2}
    assert result.trace[0].algorithm == "Priority+Aging"


def test_round_robin_known_workload() -> None:
    specs = [TaskSpec("A", 0, 4), TaskSpec("B", 1, 3)]
    result = round_robin(specs, quantum=2)

    assert result.order == ["A", "B"]
    assert result.finish == {"A": 6, "B": 7}
    assert result.waiting == {"A": 2, "B": 3}
    assert [(s.task_id, s.start, s.end) for s in result.timeline] == [
        ("A", 0, 2),
        ("B", 2, 4),
        ("A", 4, 6),
        ("B", 6, 7),
    ]


def test_trace_labels_skill_and_algorithm_separately() -> None:
    result = run_scheduler("sjf", [TaskSpec("A", 0, 1)])
    step = result.trace[0]

    assert step.skill == "schedule_tasks"
    assert step.algorithm == "SJF"
    assert step.package.startswith("core.algorithms")
    assert step.output["selected"] == "A"


def test_invalid_task_spec_is_rejected() -> None:
    with pytest.raises(ValueError):
        TaskSpec("A", 0, 0)
    with pytest.raises(ValueError):
        TaskSpec("A", -1, 1)


def test_unknown_scheduler_is_rejected() -> None:
    with pytest.raises(ValueError):
        run_scheduler("does-not-exist", [])
