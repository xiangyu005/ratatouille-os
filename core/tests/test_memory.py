"""Tests for reference OS memory and storage partition allocation algorithms."""

from __future__ import annotations

import pytest

from core.algorithms.memory import (
    ALGORITHM_INFO,
    ALGORITHMS,
    BlockSpec,
    MemoryRequest,
    best_fit,
    first_fit,
    run_memory,
    worst_fit,
)


def get_silberschatz_workload() -> tuple[list[BlockSpec], list[MemoryRequest]]:
    """Standard OS textbook workload (Silberschatz Chapter 9):

    Partitions: 100 KB, 500 KB, 200 KB, 300 KB, 600 KB (in order)
    Processes: 212 KB, 417 KB, 112 KB, 426 KB (in order)
    """
    blocks = [
        BlockSpec("B1", 100),
        BlockSpec("B2", 500),
        BlockSpec("B3", 200),
        BlockSpec("B4", 300),
        BlockSpec("B5", 600),
    ]
    requests = [
        MemoryRequest("P1", 212),
        MemoryRequest("P2", 417),
        MemoryRequest("P3", 112),
        MemoryRequest("P4", 426),
    ]
    return blocks, requests


def test_silberschatz_fixed_partition_first_fit() -> None:
    blocks, requests = get_silberschatz_workload()
    res = first_fit(blocks, requests, dynamic=False)

    assert res.algorithm == "First-Fit"
    assert res.allocations["P1"] == "B2"  # 212 into 500
    assert res.allocations["P2"] == "B5"  # 417 into 600
    assert res.allocations["P3"] == "B3"  # 112 into 200 (B1 is 100, too small)
    assert res.allocations["P4"] is None  # 426 cannot fit in remaining B1(100) or B4(300)
    assert res.metrics["success_rate"] == 0.75
    assert res.metrics["internal_fragmentation"] == (500 - 212) + (600 - 417) + (200 - 112)


def test_silberschatz_fixed_partition_best_fit() -> None:
    blocks, requests = get_silberschatz_workload()
    res = best_fit(blocks, requests, dynamic=False)

    assert res.algorithm == "Best-Fit"
    # Best-fit achieves 100% allocation for this workload!
    assert res.allocations["P1"] == "B4"  # 212 into 300 (smallest >= 212)
    assert res.allocations["P2"] == "B2"  # 417 into 500 (smallest >= 417)
    assert res.allocations["P3"] == "B3"  # 112 into 200 (smallest >= 112)
    assert res.allocations["P4"] == "B5"  # 426 into 600 (smallest >= 426)
    assert res.metrics["success_rate"] == 1.0
    assert res.metrics["free_memory"] == 100  # only B1 left free


def test_silberschatz_fixed_partition_worst_fit() -> None:
    blocks, requests = get_silberschatz_workload()
    res = worst_fit(blocks, requests, dynamic=False)

    assert res.algorithm == "Worst-Fit"
    assert res.allocations["P1"] == "B5"  # 212 into 600 (largest)
    assert res.allocations["P2"] == "B2"  # 417 into 500 (largest remaining)
    assert res.allocations["P3"] == "B4"  # 112 into 300 (largest among 100, 200, 300)
    assert res.allocations["P4"] is None  # 426 cannot fit in 100 or 200
    assert res.metrics["success_rate"] == 0.75


def test_dynamic_partition_splitting() -> None:
    # Single large storage block of 1000 units
    blocks = [BlockSpec("fridge_main", 1000)]
    requests = [
        MemoryRequest("tomatoes", 200),
        MemoryRequest("cheese", 300),
    ]
    res = first_fit(blocks, requests, dynamic=True)

    assert res.metrics["success_rate"] == 1.0
    assert res.allocations["tomatoes"] == "fridge_main"
    # The leftover of 800 was split into fridge_main_sub1, where cheese was placed
    assert res.allocations["cheese"] == "fridge_main_sub1"

    # Blocks should now have 3 segments: 200 (tomatoes), 300 (cheese), 500 (free)
    assert len(res.blocks) == 3
    assert res.blocks[0].size == 200
    assert res.blocks[0].allocated_to == "tomatoes"
    assert res.blocks[1].size == 300
    assert res.blocks[1].allocated_to == "cheese"
    assert res.blocks[2].size == 500
    assert res.blocks[2].is_free
    assert res.free_memory == 500
    assert res.allocated_memory == 500


def test_empty_requests_and_blocks() -> None:
    empty_res = first_fit([], [])
    assert empty_res.total_memory == 0
    assert empty_res.metrics["success_rate"] == 0.0

    blocks = [BlockSpec("B1", 100)]
    res = best_fit(blocks, [])
    assert res.total_memory == 100
    assert res.free_memory == 100
    assert res.metrics["success_rate"] == 0.0


def test_invalid_sizes_raise() -> None:
    with pytest.raises(ValueError, match="block size must be > 0"):
        first_fit([BlockSpec("B1", 0)], [MemoryRequest("P1", 10)])

    with pytest.raises(ValueError, match="request size must be > 0"):
        best_fit([BlockSpec("B1", 100)], [MemoryRequest("P1", -5)])


def test_run_memory_dispatcher_and_trace() -> None:
    assert len(ALGORITHMS) == 3
    assert len(ALGORITHM_INFO) == 3

    blocks = [BlockSpec("B1", 50)]
    requests = [MemoryRequest("R1", 20)]
    res = run_memory("first_fit", blocks, requests)
    assert res.allocations["R1"] == "B1"

    d = res.to_dict()
    assert d["algorithm"] == "First-Fit"
    assert len(d["trace"]) == 1
    trace_step = d["trace"][0]
    assert trace_step["skill"] == "allocate_memory"
    assert trace_step["package"] == "core.algorithms.memory"
    assert trace_step["output"]["allocated"] is True

    with pytest.raises(ValueError, match="unknown memory allocation algorithm"):
        run_memory("quantum_fit", blocks, requests)

