"""Tests for the reference cache and page replacement algorithms."""

from __future__ import annotations

import pytest

from core.algorithms.caching import (
    ALGORITHM_INFO,
    ALGORITHMS,
    clock,
    fifo,
    lfu,
    lru,
    opt,
    run_caching,
)


# Standard OS textbook reference string (Silberschatz)
# Length: 20, capacity: 3
SILBERSCHATZ_REFS = [
    "7", "0", "1", "2", "0", "3", "0", "4", "2", "3",
    "0", "3", "2", "1", "2", "0", "1", "7", "0", "1"
]


def test_fifo_silberschatz_reference() -> None:
    result = fifo(SILBERSCHATZ_REFS, capacity=3)
    # Silberschatz: 15 page faults (misses), 5 hits
    assert result.misses == 15
    assert result.hits == 5
    assert result.hit_rate == pytest.approx(5 / 20)
    assert result.metrics["miss_rate"] == pytest.approx(15 / 20)
    assert len(result.steps) == 20
    assert len(result.trace) == 20
    assert result.algorithm == "FIFO"


def test_lru_silberschatz_reference() -> None:
    result = lru(SILBERSCHATZ_REFS, capacity=3)
    # Silberschatz: 12 page faults (misses), 8 hits
    assert result.misses == 12
    assert result.hits == 8
    assert result.hit_rate == pytest.approx(8 / 20)
    assert result.algorithm == "LRU"


def test_opt_silberschatz_reference() -> None:
    result = opt(SILBERSCHATZ_REFS, capacity=3)
    # Silberschatz: 9 page faults (misses), 11 hits
    assert result.misses == 9
    assert result.hits == 11
    assert result.hit_rate == pytest.approx(11 / 20)
    assert result.algorithm == "OPT"


def test_lfu_tie_breaking_and_frequency() -> None:
    # A(1), B(1), A(2), C(1 evicts B), D(1 evicts C), A(3), B(1 evicts D)
    refs = ["A", "B", "A", "C", "D", "A", "B"]
    result = lfu(refs, capacity=2)

    assert result.hits == 2  # A at step 3, A at step 6
    assert result.misses == 5
    # Check eviction on step 4: B has count 1, A has count 2 -> B evicted
    assert result.steps[3].reference == "C"
    assert result.steps[3].evicted == "B"
    # Check eviction on step 5: C has count 1, A has count 2 -> C evicted
    assert result.steps[4].reference == "D"
    assert result.steps[4].evicted == "C"
    # Check eviction on step 7: D has count 1, A has count 3 -> D evicted
    assert result.steps[6].reference == "B"
    assert result.steps[6].evicted == "D"


def test_clock_second_chance_behavior() -> None:
    # Initial fill: A, B, C (all ref bits set to 1)
    # Hit on A (ref bit remains 1)
    # Miss on D: cycles 0->1->2, clearing ref bits to 0, then replaces slot 0 (A)
    refs = ["A", "B", "C", "A", "D"]
    result = clock(refs, capacity=3)

    assert result.hits == 1
    assert result.misses == 4
    step5 = result.steps[4]
    assert step5.reference == "D"
    assert step5.evicted == "A"
    assert set(step5.slots) == {"D", "B", "C"}


def test_empty_reference_stream() -> None:
    for name, fn in ALGORITHMS.items():
        res = fn([], capacity=3)
        assert res.hits == 0
        assert res.misses == 0
        assert res.hit_rate == 0.0
        assert res.steps == []
        assert res.trace == []


def test_all_hits_workload() -> None:
    refs = ["onion", "onion", "onion", "onion"]
    result = lru(refs, capacity=1)
    assert result.hits == 3
    assert result.misses == 1
    assert result.hit_rate == 0.75


def test_capacity_validation() -> None:
    with pytest.raises(ValueError, match="capacity must be > 0"):
        fifo(["A"], capacity=0)

    with pytest.raises(ValueError, match="capacity must be > 0"):
        lru(["A"], capacity=-1)


def test_run_caching_dispatcher_and_registry() -> None:
    assert len(ALGORITHMS) == 5
    assert len(ALGORITHM_INFO) == 5

    res = run_caching("LRU", ["A", "B", "A"], capacity=2)
    assert res.hits == 1
    assert res.misses == 2

    with pytest.raises(ValueError, match="unknown caching algorithm"):
        run_caching("non_existent", ["A"], capacity=2)


def test_trace_step_format_and_serialization() -> None:
    res = run_caching("fifo", ["tomato", "cheese"], capacity=1)
    d = res.to_dict()

    assert d["algorithm"] == "FIFO"
    assert d["capacity"] == 1
    assert len(d["trace"]) == 2
    step0 = d["trace"][0]
    assert step0["skill"] == "cache_replacement"
    assert step0["package"] == "core.algorithms.caching"
    assert "slots" in step0["input"]
    assert "hit" in step0["output"]

