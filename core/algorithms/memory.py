"""Reference OS memory and storage partition allocation algorithms.

Pure functions only: no DB, FastAPI, NumPy or Numba.
Implements First Fit, Best Fit, and Worst Fit partition allocation for restaurant
storage spaces, refrigerators, and prep stations (docs/03 G02, docs/21 §7).
Supports both fixed-partition (slots) and dynamic-partition (splitting) allocation.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class BlockSpec:
    id: str
    size: int
    start: int = 0
    allocated_to: str | None = None

    @property
    def is_free(self) -> bool:
        return self.allocated_to is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "size": self.size,
            "start": self.start,
            "allocated_to": self.allocated_to,
            "is_free": self.is_free,
        }


@dataclass(frozen=True)
class MemoryRequest:
    id: str
    size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "size": self.size,
        }


@dataclass(frozen=True)
class MemoryStep:
    step: int
    request_id: str
    size: int
    allocated: bool
    block_id: str | None
    free_blocks: list[dict[str, Any]]
    internal_fragmentation: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "request_id": self.request_id,
            "size": self.size,
            "allocated": self.allocated,
            "block_id": self.block_id,
            "free_blocks": self.free_blocks,
            "internal_fragmentation": self.internal_fragmentation,
        }


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
class MemoryResult:
    algorithm: str
    total_memory: int
    allocated_memory: int
    free_memory: int
    allocations: dict[str, str | None]
    blocks: list[BlockSpec]
    steps: list[MemoryStep]
    trace: list[TraceStep]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "total_memory": self.total_memory,
            "allocated_memory": self.allocated_memory,
            "free_memory": self.free_memory,
            "allocations": dict(self.allocations),
            "blocks": [b.to_dict() for b in self.blocks],
            "steps": [s.to_dict() for s in self.steps],
            "trace": [t.to_dict() for t in self.trace],
            "metrics": self.metrics,
        }


def _validate_inputs(blocks: list[BlockSpec], requests: list[MemoryRequest]) -> None:
    for b in blocks:
        if b.size <= 0:
            raise ValueError(f"block size must be > 0, got {b.size} for block {b.id}")
    for r in requests:
        if r.size <= 0:
            raise ValueError(f"request size must be > 0, got {r.size} for request {r.id}")


def _clone_blocks(blocks: list[BlockSpec]) -> list[BlockSpec]:
    current_offset = 0
    cloned: list[BlockSpec] = []
    for b in blocks:
        offset = b.start if b.start != 0 or not cloned else current_offset
        cloned.append(
            BlockSpec(
                id=b.id,
                size=b.size,
                start=offset,
                allocated_to=b.allocated_to,
            )
        )
        current_offset = offset + b.size
    return cloned


def _compute_metrics(
    total_memory: int,
    allocated_memory: int,
    free_memory: int,
    allocated_count: int,
    total_requests: int,
    internal_frag: int,
    external_frag: int,
) -> dict[str, float]:
    success_rate = (allocated_count / total_requests) if total_requests > 0 else 0.0
    allocated_ratio = (allocated_memory / total_memory) if total_memory > 0 else 0.0
    free_ratio = (free_memory / total_memory) if total_memory > 0 else 0.0
    return {
        "total_memory": float(total_memory),
        "allocated_memory": float(allocated_memory),
        "free_memory": float(free_memory),
        "success_rate": success_rate,
        "allocated_ratio": allocated_ratio,
        "free_ratio": free_ratio,
        "internal_fragmentation": float(internal_frag),
        "external_fragmentation": float(external_frag),
    }


def _run_allocation(
    algorithm_name: str,
    blocks: list[BlockSpec],
    requests: list[MemoryRequest],
    selector_fn: Callable[[list[BlockSpec], MemoryRequest], int | None],
    dynamic: bool,
) -> MemoryResult:
    _validate_inputs(blocks, requests)
    active_blocks = _clone_blocks(blocks)
    total_memory = sum(b.size for b in active_blocks)

    if not requests:
        allocated_mem = sum(b.size for b in active_blocks if not b.is_free)
        free_mem = total_memory - allocated_mem
        metrics = _compute_metrics(
            total_memory=total_memory,
            allocated_memory=allocated_mem,
            free_memory=free_mem,
            allocated_count=0,
            total_requests=0,
            internal_frag=0,
            external_frag=0,
        )
        return MemoryResult(
            algorithm=algorithm_name,
            total_memory=total_memory,
            allocated_memory=allocated_mem,
            free_memory=free_mem,
            allocations={},
            blocks=active_blocks,
            steps=[],
            trace=[],
            metrics=metrics,
        )

    allocations: dict[str, str | None] = {}
    steps: list[MemoryStep] = []
    trace: list[TraceStep] = []
    allocated_count = 0
    total_internal_frag = 0
    split_counter = 0

    for idx, req in enumerate(requests, start=1):
        free_snapshot = [
            {"id": b.id, "size": b.size, "start": b.start}
            for b in active_blocks
            if b.is_free
        ]

        target_idx = selector_fn(active_blocks, req)

        if target_idx is not None:
            target_block = active_blocks[target_idx]
            allocations[req.id] = target_block.id
            allocated_count += 1
            allocated = True
            chosen_block_id = target_block.id

            if dynamic:
                leftover = target_block.size - req.size
                target_block.size = req.size
                target_block.allocated_to = req.id
                step_internal_frag = 0

                if leftover > 0:
                    split_counter += 1
                    split_block = BlockSpec(
                        id=f"{chosen_block_id}_sub{split_counter}",
                        size=leftover,
                        start=target_block.start + req.size,
                        allocated_to=None,
                    )
                    active_blocks.insert(target_idx + 1, split_block)
            else:
                step_internal_frag = target_block.size - req.size
                total_internal_frag += step_internal_frag
                target_block.allocated_to = req.id
        else:
            allocations[req.id] = None
            allocated = False
            chosen_block_id = None
            step_internal_frag = 0

        steps.append(
            MemoryStep(
                step=idx,
                request_id=req.id,
                size=req.size,
                allocated=allocated,
                block_id=chosen_block_id,
                free_blocks=free_snapshot,
                internal_fragmentation=step_internal_frag,
            )
        )

        trace.append(
            TraceStep(
                step=idx,
                skill="allocate_memory",
                algorithm=algorithm_name,
                package="core.algorithms.memory",
                input={
                    "request_id": req.id,
                    "size": req.size,
                    "dynamic": dynamic,
                    "free_blocks": free_snapshot,
                },
                output={
                    "allocated": allocated,
                    "block_id": chosen_block_id,
                    "internal_fragmentation": step_internal_frag,
                },
            )
        )

    # Compute final metrics
    allocated_mem = sum(b.size for b in active_blocks if not b.is_free)
    free_mem = sum(b.size for b in active_blocks if b.is_free)

    # External fragmentation: total free space if there were unallocated requests that could have fit in total free space
    unallocated_reqs = [r for r in requests if allocations[r.id] is None]
    external_frag = 0
    if unallocated_reqs and free_mem >= min(r.size for r in unallocated_reqs):
        external_frag = free_mem

    metrics = _compute_metrics(
        total_memory=total_memory,
        allocated_memory=allocated_mem,
        free_memory=free_mem,
        allocated_count=allocated_count,
        total_requests=len(requests),
        internal_frag=total_internal_frag,
        external_frag=external_frag,
    )

    return MemoryResult(
        algorithm=algorithm_name,
        total_memory=total_memory,
        allocated_memory=allocated_mem,
        free_memory=free_mem,
        allocations=allocations,
        blocks=active_blocks,
        steps=steps,
        trace=trace,
        metrics=metrics,
    )


def first_fit(
    blocks: list[BlockSpec],
    requests: list[MemoryRequest],
    dynamic: bool = False,
) -> MemoryResult:
    """First-Fit: Allocates the first free hole large enough for the request."""
    def _select(active: list[BlockSpec], req: MemoryRequest) -> int | None:
        for i, b in enumerate(active):
            if b.is_free and b.size >= req.size:
                return i
        return None

    return _run_allocation("First-Fit", blocks, requests, _select, dynamic=dynamic)


def best_fit(
    blocks: list[BlockSpec],
    requests: list[MemoryRequest],
    dynamic: bool = False,
) -> MemoryResult:
    """Best-Fit: Allocates the smallest free hole large enough for the request."""
    def _select(active: list[BlockSpec], req: MemoryRequest) -> int | None:
        best_idx: int | None = None
        best_size: int | None = None
        for i, b in enumerate(active):
            if b.is_free and b.size >= req.size:
                if best_size is None or b.size < best_size:
                    best_size = b.size
                    best_idx = i
        return best_idx

    return _run_allocation("Best-Fit", blocks, requests, _select, dynamic=dynamic)


def worst_fit(
    blocks: list[BlockSpec],
    requests: list[MemoryRequest],
    dynamic: bool = False,
) -> MemoryResult:
    """Worst-Fit: Allocates the largest free hole available (leaving the largest remnant)."""
    def _select(active: list[BlockSpec], req: MemoryRequest) -> int | None:
        worst_idx: int | None = None
        worst_size: int | None = None
        for i, b in enumerate(active):
            if b.is_free and b.size >= req.size:
                if worst_size is None or b.size > worst_size:
                    worst_size = b.size
                    worst_idx = i
        return worst_idx

    return _run_allocation("Worst-Fit", blocks, requests, _select, dynamic=dynamic)


ALGORITHMS: dict[str, Callable[..., MemoryResult]] = {
    "first_fit": first_fit,
    "best_fit": best_fit,
    "worst_fit": worst_fit,
}

ALGORITHM_INFO = [
    {
        "name": "first_fit",
        "label": "First-Fit",
        "description": "Allocates the first partition/hole large enough",
    },
    {
        "name": "best_fit",
        "label": "Best-Fit",
        "description": "Allocates the smallest partition/hole that fits, minimizing immediate leftover",
    },
    {
        "name": "worst_fit",
        "label": "Worst-Fit",
        "description": "Allocates the largest partition/hole, leaving the largest remnant for later",
    },
]


def run_memory(
    algorithm: str,
    blocks: list[BlockSpec],
    requests: list[MemoryRequest],
    dynamic: bool = False,
) -> MemoryResult:
    key = algorithm.lower().replace("-", "_").strip()
    if key not in ALGORITHMS:
        raise ValueError(
            f"unknown memory allocation algorithm {algorithm!r}; available: {sorted(ALGORITHMS)}"
        )
    return ALGORITHMS[key](blocks, requests, dynamic=dynamic)

