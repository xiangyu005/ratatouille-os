"""Tests for reference OS deadlock avoidance and detection algorithms."""

from __future__ import annotations

import pytest

from core.algorithms.deadlock import (
    ALGORITHM_INFO,
    ALGORITHMS,
    bankers_request,
    bankers_safety,
    detect_deadlock_matrix,
    detect_deadlock_wfg,
)


def get_silberschatz_bankers_setup() -> tuple[
    dict[str, int], dict[str, dict[str, int]], dict[str, dict[str, int]]
]:
    """Standard OS textbook example (Silberschatz Chapter 8, Banker's Algorithm):

    5 processes: P0, P1, P2, P3, P4
    3 resource types: A (10), B (5), C (7)
    """
    available = {"A": 3, "B": 3, "C": 2}
    max_demand = {
        "P0": {"A": 7, "B": 5, "C": 3},
        "P1": {"A": 3, "B": 2, "C": 2},
        "P2": {"A": 9, "B": 0, "C": 2},
        "P3": {"A": 2, "B": 2, "C": 2},
        "P4": {"A": 4, "B": 3, "C": 3},
    }
    allocation = {
        "P0": {"A": 0, "B": 1, "C": 0},
        "P1": {"A": 2, "B": 0, "C": 0},
        "P2": {"A": 3, "B": 0, "C": 2},
        "P3": {"A": 2, "B": 1, "C": 1},
        "P4": {"A": 0, "B": 0, "C": 2},
    }
    return available, max_demand, allocation


def test_bankers_safety_silberschatz_example() -> None:
    available, max_demand, allocation = get_silberschatz_bankers_setup()
    result = bankers_safety(available, max_demand, allocation)

    assert result.is_safe is True
    # Verify that safe_sequence includes all 5 processes and satisfies the execution constraints
    assert len(result.safe_sequence) == 5
    assert set(result.safe_sequence) == {"P0", "P1", "P2", "P3", "P4"}
    assert result.unresolved_processes == []
    # P1 should execute first under the standard tie-breaker
    assert result.safe_sequence[0] == "P1"


def test_bankers_request_grant_safe() -> None:
    available, max_demand, allocation = get_silberschatz_bankers_setup()
    # P1 requests (1, 0, 2): textbook states this request can immediately be granted
    req = {"A": 1, "B": 0, "C": 2}
    result = bankers_request("P1", req, available, max_demand, allocation)

    assert result.granted is True
    assert result.safety is not None
    assert result.safety.is_safe is True
    assert "safe" in result.reason.lower()


def test_bankers_request_exceeds_claim() -> None:
    available, max_demand, allocation = get_silberschatz_bankers_setup()
    # P0 requests more than its need: need for B is (5 - 1) = 4; request 5 exceeds claim
    req = {"A": 0, "B": 5, "C": 0}
    result = bankers_request("P0", req, available, max_demand, allocation)

    assert result.granted is False
    assert "exceeded maximum claim" in result.reason


def test_bankers_request_exceeds_available() -> None:
    available, max_demand, allocation = get_silberschatz_bankers_setup()
    # P4 requests A=4, but Available has only 3
    req = {"A": 4, "B": 0, "C": 0}
    result = bankers_request("P4", req, available, max_demand, allocation)

    assert result.granted is False
    assert "must wait" in result.reason


def test_bankers_request_denied_due_to_unsafe_state() -> None:
    available, max_demand, allocation = get_silberschatz_bankers_setup()
    # If P0 requests (0, 3, 0), remaining available B becomes 0.
    # Every process needs at least one B except P2 (which needs A=6 > 3).
    # Thus no process can finish, leading to an unsafe state.
    req = {"A": 0, "B": 3, "C": 0}
    result = bankers_request("P0", req, available, max_demand, allocation)

    assert result.granted is False
    assert "unsafe state" in result.reason.lower()


def test_bankers_sequential_requests_silberschatz() -> None:
    """Exact Silberschatz sequence:

    1. P1 requests (1, 0, 2) -> GRANTED.
    2. Then P0 requests (0, 2, 0) -> DENIED (unsafe: leaves available (2, 1, 0) where C=0 blocks P3).
    """
    available, max_demand, allocation = get_silberschatz_bankers_setup()

    # Step 1: P1 request (1, 0, 2) granted
    req1 = {"A": 1, "B": 0, "C": 2}
    res1 = bankers_request("P1", req1, available, max_demand, allocation)
    assert res1.granted is True

    # Mutate to state after P1's request
    available["A"] -= 1
    available["C"] -= 2
    allocation["P1"]["A"] += 1
    allocation["P1"]["C"] += 2

    # Step 2: Now P0 requests (0, 2, 0)
    req2 = {"A": 0, "B": 2, "C": 0}
    res2 = bankers_request("P0", req2, available, max_demand, allocation)
    assert res2.granted is False
    assert "unsafe state" in res2.reason.lower()


def test_detect_deadlock_wfg_cycle() -> None:
    # Single-instance cycle: T1 -> T2 -> T1
    wait_for = {
        "T1": ["T2"],
        "T2": ["T1"],
        "T3": ["T1"],  # T3 waiting on T1
    }
    result = detect_deadlock_wfg(wait_for)

    assert result.has_deadlock is True
    assert set(result.deadlocked_processes) == {"T1", "T2"}
    assert len(result.cycles) >= 1
    assert result.metrics["deadlocked_count"] == 2.0


def test_detect_deadlock_wfg_no_cycle() -> None:
    # DAG: T1 -> T2 -> T3
    wait_for = {
        "T1": ["T2"],
        "T2": ["T3"],
        "T3": [],
    }
    result = detect_deadlock_wfg(wait_for)

    assert result.has_deadlock is False
    assert result.deadlocked_processes == []
    assert result.cycles == []


def test_detect_deadlock_matrix_deadlocked() -> None:
    # 3 processes, 2 resource types: R1 (stoves), R2 (sinks)
    # P1 holds R1, requests R2
    # P2 holds R2, requests R1
    # Available = 0
    available = {"R1": 0, "R2": 0}
    allocation = {
        "P1": {"R1": 1, "R2": 0},
        "P2": {"R1": 0, "R2": 1},
    }
    request = {
        "P1": {"R1": 0, "R2": 1},
        "P2": {"R1": 1, "R2": 0},
    }
    result = detect_deadlock_matrix(available, allocation, request)

    assert result.has_deadlock is True
    assert set(result.deadlocked_processes) == {"P1", "P2"}


def test_detect_deadlock_matrix_resolvable() -> None:
    # P1 can finish using available resources and then release its allocation to allow P2 to finish
    available = {"R1": 1, "R2": 0}
    allocation = {
        "P1": {"R1": 0, "R2": 1},
        "P2": {"R1": 1, "R2": 0},
    }
    request = {
        "P1": {"R1": 1, "R2": 0},  # can be satisfied immediately by Available
        "P2": {"R1": 0, "R2": 1},  # waiting for P1 to release R2
    }
    result = detect_deadlock_matrix(available, allocation, request)

    assert result.has_deadlock is False
    assert result.deadlocked_processes == []


def test_deadlock_algorithm_info_and_serialization() -> None:
    assert len(ALGORITHMS) == 4
    assert len(ALGORITHM_INFO) == 4

    available, max_demand, allocation = get_silberschatz_bankers_setup()
    res = bankers_safety(available, max_demand, allocation)
    d = res.to_dict()

    assert d["is_safe"] is True
    assert len(d["safe_sequence"]) == 5
    assert len(d["trace"]) == 5
    assert d["trace"][0]["skill"] == "resource_management"
    assert d["trace"][0]["package"] == "core.algorithms.deadlock"
