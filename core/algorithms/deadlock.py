"""Reference OS deadlock avoidance and detection algorithms.

Pure functions only: no DB, FastAPI, NumPy or Numba.
Implements:
1. Dijkstra's Banker's Algorithm (safety check and resource-request algorithm)
2. Deadlock Detection (Wait-For Graph cycle detection and Multiple-Instance Detection)
As specified in docs/03 G03 and docs/21 §7 for kitchen equipment and station resource safety.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable


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
class SafetyResult:
    is_safe: bool
    safe_sequence: list[str]
    work_history: list[dict[str, int]]
    trace: list[TraceStep]
    unresolved_processes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "safe_sequence": list(self.safe_sequence),
            "work_history": [dict(w) for w in self.work_history],
            "trace": [t.to_dict() for t in self.trace],
            "unresolved_processes": list(self.unresolved_processes),
        }


@dataclass
class BankerRequestResult:
    granted: bool
    reason: str
    safety: SafetyResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "granted": self.granted,
            "reason": self.reason,
            "safety": self.safety.to_dict() if self.safety else None,
        }


@dataclass
class DeadlockDetectionResult:
    has_deadlock: bool
    deadlocked_processes: list[str]
    cycles: list[list[str]]
    trace: list[TraceStep]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_deadlock": self.has_deadlock,
            "deadlocked_processes": list(self.deadlocked_processes),
            "cycles": [list(c) for c in self.cycles],
            "trace": [t.to_dict() for t in self.trace],
            "metrics": self.metrics,
        }


def _normalize_resources(
    available: dict[str, int],
    max_demand: dict[str, dict[str, int]],
    allocation: dict[str, dict[str, int]],
) -> tuple[list[str], list[str]]:
    """Validate resource consistency and return sorted resource names and process names."""
    all_res = set(available.keys())
    for d in max_demand.values():
        all_res.update(d.keys())
    for d in allocation.values():
        all_res.update(d.keys())

    res_names = sorted(all_res)
    processes = sorted(set(max_demand.keys()) | set(allocation.keys()))

    for r in res_names:
        if available.get(r, 0) < 0:
            raise ValueError(f"available resource {r} cannot be negative")

    for p in processes:
        p_max = max_demand.get(p, {})
        p_alloc = allocation.get(p, {})
        for r in res_names:
            alloc_val = p_alloc.get(r, 0)
            max_val = p_max.get(r, 0)
            if alloc_val < 0 or max_val < 0:
                raise ValueError(f"process {p} has negative claim or allocation for {r}")
            if alloc_val > max_val:
                raise ValueError(
                    f"process {p} allocated {alloc_val} exceeds maximum claim {max_val} for {r}"
                )

    return res_names, processes


def bankers_safety(
    available: dict[str, int],
    max_demand: dict[str, dict[str, int]],
    allocation: dict[str, dict[str, int]],
) -> SafetyResult:
    """Dijkstra's Banker's Safety Algorithm."""
    res_names, processes = _normalize_resources(available, max_demand, allocation)

    if not processes:
        return SafetyResult(
            is_safe=True,
            safe_sequence=[],
            work_history=[dict(available)],
            trace=[],
            unresolved_processes=[],
        )

    # Calculate Need matrix: Need[p][r] = Max[p][r] - Alloc[p][r]
    need: dict[str, dict[str, int]] = {
        p: {r: max_demand.get(p, {}).get(r, 0) - allocation.get(p, {}).get(r, 0) for r in res_names}
        for p in processes
    }

    work: dict[str, int] = {r: available.get(r, 0) for r in res_names}
    finish: dict[str, bool] = {p: False for p in processes}
    safe_sequence: list[str] = []
    work_history: list[dict[str, int]] = [dict(work)]
    trace: list[TraceStep] = []

    step = 0
    while True:
        # Find an unfinished process p whose need <= work
        found = False
        for p in processes:
            if not finish[p]:
                # Check if need[p][r] <= work[r] for all r
                if all(need[p][r] <= work[r] for r in res_names):
                    step += 1
                    input_work = dict(work)
                    # Pretend process finishes and releases allocation
                    for r in res_names:
                        work[r] += allocation.get(p, {}).get(r, 0)
                    finish[p] = True
                    safe_sequence.append(p)
                    work_history.append(dict(work))
                    found = True

                    trace.append(
                        TraceStep(
                            step=step,
                            skill="resource_management",
                            algorithm="Bankers-Safety",
                            package="core.algorithms.deadlock",
                            input={
                                "candidate_process": p,
                                "work_before": input_work,
                                "need": dict(need[p]),
                                "allocation": dict(allocation.get(p, {})),
                            },
                            output={
                                "finish": True,
                                "work_after": dict(work),
                                "safe_sequence": list(safe_sequence),
                            },
                        )
                    )
                    break  # Restart loop with new work

        if not found:
            break

    is_safe = all(finish.values())
    unresolved = [p for p in processes if not finish[p]]

    return SafetyResult(
        is_safe=is_safe,
        safe_sequence=safe_sequence if is_safe else [],
        work_history=work_history,
        trace=trace,
        unresolved_processes=unresolved,
    )


def bankers_request(
    process_id: str,
    request: dict[str, int],
    available: dict[str, int],
    max_demand: dict[str, dict[str, int]],
    allocation: dict[str, dict[str, int]],
) -> BankerRequestResult:
    """Dijkstra's Banker's Resource-Request Algorithm."""
    res_names, processes = _normalize_resources(available, max_demand, allocation)
    if process_id not in processes:
        raise ValueError(f"unknown process {process_id!r}")

    p_need = {
        r: max_demand.get(process_id, {}).get(r, 0) - allocation.get(process_id, {}).get(r, 0)
        for r in res_names
    }

    # 1. If Request_i > Need_i: Error condition (exceeded claim)
    for r in res_names:
        req_val = request.get(r, 0)
        if req_val < 0:
            raise ValueError(f"request amount for {r} cannot be negative")
        if req_val > p_need[r]:
            return BankerRequestResult(
                granted=False,
                reason=f"Process {process_id} exceeded maximum claim for resource {r} (requested {req_val} > need {p_need[r]})",
            )

    # 2. If Request_i > Available: Process must wait
    for r in res_names:
        req_val = request.get(r, 0)
        avail_val = available.get(r, 0)
        if req_val > avail_val:
            return BankerRequestResult(
                granted=False,
                reason=f"Insufficient resource {r} available (requested {req_val} > available {avail_val}); process must wait",
            )

    # 3. Pretend to allocate requested resources
    temp_available = dict(available)
    temp_allocation = copy.deepcopy(allocation)

    for r in res_names:
        req_val = request.get(r, 0)
        temp_available[r] -= req_val
        temp_allocation.setdefault(process_id, {})[r] = (
            temp_allocation.get(process_id, {}).get(r, 0) + req_val
        )

    # 4. Check safety
    safety = bankers_safety(temp_available, max_demand, temp_allocation)

    if safety.is_safe:
        return BankerRequestResult(
            granted=True,
            reason="Request granted: resulting state is safe",
            safety=safety,
        )
    else:
        return BankerRequestResult(
            granted=False,
            reason="Request denied: granting would result in an unsafe state",
            safety=safety,
        )


def detect_deadlock_wfg(wait_for: dict[str, list[str]]) -> DeadlockDetectionResult:
    """Deadlock detection on a Wait-For Graph (WFG) using cycle detection."""
    # Graph nodes are all processes present as keys or in adjacency lists
    nodes = sorted(set(wait_for.keys()) | {p for targets in wait_for.values() for p in targets})
    adj: dict[str, list[str]] = {node: list(wait_for.get(node, [])) for node in nodes}

    # Tarjan or DFS cycle detection
    visited: dict[str, int] = {node: 0 for node in nodes}  # 0: unvisited, 1: active, 2: finished
    path: list[str] = []
    cycles: list[list[str]] = []
    deadlocked: set[str] = set()
    trace: list[TraceStep] = []
    step = 0

    def dfs(curr: str) -> None:
        nonlocal step
        visited[curr] = 1
        path.append(curr)

        for neighbor in sorted(adj.get(curr, [])):
            if visited[neighbor] == 1:
                # Found cycle
                cycle_start_idx = path.index(neighbor)
                cycle = path[cycle_start_idx:] + [neighbor]
                cycles.append(cycle)
                for node in cycle[:-1]:
                    deadlocked.add(node)

                step += 1
                trace.append(
                    TraceStep(
                        step=step,
                        skill="resource_management",
                        algorithm="WFG-Cycle-Detection",
                        package="core.algorithms.deadlock",
                        input={"node": curr, "neighbor": neighbor, "path": list(path)},
                        output={"cycle_detected": True, "cycle": list(cycle)},
                    )
                )
            elif visited[neighbor] == 0:
                dfs(neighbor)

        path.pop()
        visited[curr] = 2

    for n in nodes:
        if visited[n] == 0:
            dfs(n)

    has_deadlock = len(deadlocked) > 0
    metrics = {
        "node_count": float(len(nodes)),
        "deadlocked_count": float(len(deadlocked)),
        "cycle_count": float(len(cycles)),
    }

    return DeadlockDetectionResult(
        has_deadlock=has_deadlock,
        deadlocked_processes=sorted(deadlocked),
        cycles=cycles,
        trace=trace,
        metrics=metrics,
    )


def detect_deadlock_matrix(
    available: dict[str, int],
    allocation: dict[str, dict[str, int]],
    request: dict[str, dict[str, int]],
) -> DeadlockDetectionResult:
    """Multiple-instance resource deadlock detection algorithm (Silberschatz Chapter 8)."""
    res_names = sorted(set(available.keys()) | {r for a in allocation.values() for r in a} | {r for req in request.values() for r in req})
    processes = sorted(set(allocation.keys()) | set(request.keys()))

    if not processes:
        return DeadlockDetectionResult(
            has_deadlock=False,
            deadlocked_processes=[],
            cycles=[],
            trace=[],
            metrics={"node_count": 0.0, "deadlocked_count": 0.0, "cycle_count": 0.0},
        )

    # 1. Work = Available
    work = {r: available.get(r, 0) for r in res_names}

    # 2. Finish[i] = False if Allocation[i] != 0, else True
    finish: dict[str, bool] = {}
    for p in processes:
        p_alloc = allocation.get(p, {})
        has_alloc = any(p_alloc.get(r, 0) > 0 for r in res_names)
        finish[p] = not has_alloc

    trace: list[TraceStep] = []
    step = 0

    # 3. Find an index i such that: Finish[i] == False and Request[i] <= Work
    while True:
        found = False
        for p in processes:
            if not finish[p]:
                p_req = request.get(p, {})
                if all(p_req.get(r, 0) <= work[r] for r in res_names):
                    step += 1
                    input_work = dict(work)
                    # Reclaim resources
                    p_alloc = allocation.get(p, {})
                    for r in res_names:
                        work[r] += p_alloc.get(r, 0)
                    finish[p] = True
                    found = True

                    trace.append(
                        TraceStep(
                            step=step,
                            skill="resource_management",
                            algorithm="Matrix-Deadlock-Detection",
                            package="core.algorithms.deadlock",
                            input={"process": p, "work_before": input_work, "request": dict(p_req)},
                            output={"finish": True, "work_after": dict(work)},
                        )
                    )
                    break

        if not found:
            break

    deadlocked = [p for p in processes if not finish[p]]
    has_deadlock = len(deadlocked) > 0

    metrics = {
        "node_count": float(len(processes)),
        "deadlocked_count": float(len(deadlocked)),
        "cycle_count": float(1 if has_deadlock else 0),
    }

    return DeadlockDetectionResult(
        has_deadlock=has_deadlock,
        deadlocked_processes=sorted(deadlocked),
        cycles=[],
        trace=trace,
        metrics=metrics,
    )


ALGORITHMS = {
    "bankers_safety": bankers_safety,
    "bankers_request": bankers_request,
    "detect_deadlock_wfg": detect_deadlock_wfg,
    "detect_deadlock_matrix": detect_deadlock_matrix,
}

ALGORITHM_INFO = [
    {
        "name": "bankers_safety",
        "label": "Banker's Safety Check",
        "description": "Determines whether a multi-resource allocation state has a safe execution sequence",
    },
    {
        "name": "bankers_request",
        "label": "Banker's Resource-Request",
        "description": "Simulates request allocation and verifies resulting state safety",
    },
    {
        "name": "detect_deadlock_wfg",
        "label": "Wait-For Graph Cycle Detection",
        "description": "Finds deadlock cycles in single-instance resource wait-for graphs",
    },
    {
        "name": "detect_deadlock_matrix",
        "label": "Multiple-Instance Deadlock Detection",
        "description": "Matrix algorithm to detect deadlocked processes with multiple resource units",
    },
]

