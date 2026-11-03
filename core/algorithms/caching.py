"""Reference OS cache and page replacement algorithms.

Pure functions only: no DB, FastAPI, NumPy or Numba.
These serve as the readable reference implementations for memory/cache replacement
(FIFO, LRU, LFU, Clock, OPT) in the restaurant ingredient prep/cache area.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class CacheStep:
    step: int
    reference: str
    hit: bool
    evicted: str | None
    slots: list[str]
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "step": self.step,
            "reference": self.reference,
            "hit": self.hit,
            "evicted": self.evicted,
            "slots": list(self.slots),
        }
        if self.extra:
            result["extra"] = self.extra
        return result


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
class CacheResult:
    algorithm: str
    capacity: int
    references: list[str]
    hits: int
    misses: int
    hit_rate: float
    steps: list[CacheStep]
    trace: list[TraceStep]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "capacity": self.capacity,
            "references": list(self.references),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "steps": [s.to_dict() for s in self.steps],
            "trace": [t.to_dict() for t in self.trace],
            "metrics": self.metrics,
        }


def _validate(references: list[str], capacity: int) -> None:
    if capacity <= 0:
        raise ValueError("capacity must be > 0")


def _empty_result(algorithm: str, capacity: int) -> CacheResult:
    metrics = {
        "hits": 0.0,
        "misses": 0.0,
        "hit_rate": 0.0,
        "miss_rate": 0.0,
        "total_references": 0.0,
    }
    return CacheResult(
        algorithm=algorithm,
        capacity=capacity,
        references=[],
        hits=0,
        misses=0,
        hit_rate=0.0,
        steps=[],
        trace=[],
        metrics=metrics,
    )


def _make_metrics(hits: int, misses: int) -> dict[str, float]:
    total = hits + misses
    hit_rate = (hits / total) if total > 0 else 0.0
    miss_rate = (misses / total) if total > 0 else 0.0
    return {
        "hits": float(hits),
        "misses": float(misses),
        "hit_rate": hit_rate,
        "miss_rate": miss_rate,
        "total_references": float(total),
    }


def fifo(references: list[str], capacity: int) -> CacheResult:
    """First-In, First-Out cache replacement."""
    _validate(references, capacity)
    if not references:
        return _empty_result("FIFO", capacity)

    slots: list[str] = []
    steps: list[CacheStep] = []
    trace: list[TraceStep] = []
    hits = 0
    misses = 0

    for idx, ref in enumerate(references, start=1):
        prev_slots = list(slots)
        if ref in slots:
            hits += 1
            hit = True
            evicted = None
        else:
            misses += 1
            hit = False
            if len(slots) >= capacity:
                evicted = slots.pop(0)
            else:
                evicted = None
            slots.append(ref)

        step = CacheStep(
            step=idx,
            reference=ref,
            hit=hit,
            evicted=evicted,
            slots=list(slots),
        )
        steps.append(step)

        trace.append(
            TraceStep(
                step=idx,
                skill="cache_replacement",
                algorithm="FIFO",
                package="core.algorithms.caching",
                input={"time": idx, "reference": ref, "slots": prev_slots, "capacity": capacity},
                output={"hit": hit, "evicted": evicted, "new_slots": list(slots)},
            )
        )

    return CacheResult(
        algorithm="FIFO",
        capacity=capacity,
        references=list(references),
        hits=hits,
        misses=misses,
        hit_rate=hits / len(references),
        steps=steps,
        trace=trace,
        metrics=_make_metrics(hits, misses),
    )


def lru(references: list[str], capacity: int) -> CacheResult:
    """Least Recently Used cache replacement."""
    _validate(references, capacity)
    if not references:
        return _empty_result("LRU", capacity)

    # slots order: index 0 is least recently used, index -1 is most recently used
    slots: list[str] = []
    steps: list[CacheStep] = []
    trace: list[TraceStep] = []
    hits = 0
    misses = 0

    for idx, ref in enumerate(references, start=1):
        prev_slots = list(slots)
        if ref in slots:
            hits += 1
            hit = True
            evicted = None
            slots.remove(ref)
            slots.append(ref)
        else:
            misses += 1
            hit = False
            if len(slots) >= capacity:
                evicted = slots.pop(0)
            else:
                evicted = None
            slots.append(ref)

        step = CacheStep(
            step=idx,
            reference=ref,
            hit=hit,
            evicted=evicted,
            slots=list(slots),
        )
        steps.append(step)

        trace.append(
            TraceStep(
                step=idx,
                skill="cache_replacement",
                algorithm="LRU",
                package="core.algorithms.caching",
                input={"time": idx, "reference": ref, "slots": prev_slots, "capacity": capacity},
                output={"hit": hit, "evicted": evicted, "new_slots": list(slots)},
            )
        )

    return CacheResult(
        algorithm="LRU",
        capacity=capacity,
        references=list(references),
        hits=hits,
        misses=misses,
        hit_rate=hits / len(references),
        steps=steps,
        trace=trace,
        metrics=_make_metrics(hits, misses),
    )


def lfu(references: list[str], capacity: int) -> CacheResult:
    """Least Frequently Used cache replacement with FIFO tie-breaking."""
    _validate(references, capacity)
    if not references:
        return _empty_result("LFU", capacity)

    slots: list[str] = []
    counts: dict[str, int] = {}
    inserted_at: dict[str, int] = {}
    steps: list[CacheStep] = []
    trace: list[TraceStep] = []
    hits = 0
    misses = 0

    for idx, ref in enumerate(references, start=1):
        prev_slots = list(slots)
        if ref in slots:
            hits += 1
            hit = True
            evicted = None
            counts[ref] += 1
        else:
            misses += 1
            hit = False
            if len(slots) >= capacity:
                # Find min count; tie-break: earliest inserted_at, then alphabetical
                victim = min(
                    slots,
                    key=lambda item: (counts[item], inserted_at[item], item),
                )
                evicted = victim
                slots.remove(victim)
                del counts[victim]
                del inserted_at[victim]
            else:
                evicted = None
            slots.append(ref)
            counts[ref] = 1
            inserted_at[ref] = idx

        step = CacheStep(
            step=idx,
            reference=ref,
            hit=hit,
            evicted=evicted,
            slots=list(slots),
            extra={"counts": {k: counts[k] for k in slots}},
        )
        steps.append(step)

        trace.append(
            TraceStep(
                step=idx,
                skill="cache_replacement",
                algorithm="LFU",
                package="core.algorithms.caching",
                input={
                    "time": idx,
                    "reference": ref,
                    "slots": prev_slots,
                    "counts": {k: counts.get(k, 0) for k in prev_slots},
                    "capacity": capacity,
                },
                output={"hit": hit, "evicted": evicted, "new_slots": list(slots)},
            )
        )

    return CacheResult(
        algorithm="LFU",
        capacity=capacity,
        references=list(references),
        hits=hits,
        misses=misses,
        hit_rate=hits / len(references),
        steps=steps,
        trace=trace,
        metrics=_make_metrics(hits, misses),
    )


def clock(references: list[str], capacity: int) -> CacheResult:
    """Clock (Second Chance) page replacement algorithm."""
    _validate(references, capacity)
    if not references:
        return _empty_result("Clock", capacity)

    # Fixed physical slots: each has item and ref_bit
    slots: list[str | None] = [None] * capacity
    ref_bits: list[int] = [0] * capacity
    hand = 0
    steps: list[CacheStep] = []
    trace: list[TraceStep] = []
    hits = 0
    misses = 0

    for idx, ref in enumerate(references, start=1):
        prev_occupied = [s for s in slots if s is not None]
        initial_hand = hand

        if ref in slots:
            hits += 1
            hit = True
            evicted = None
            slot_idx = slots.index(ref)
            ref_bits[slot_idx] = 1
        else:
            misses += 1
            hit = False
            # Check if there is an empty slot available before cycling
            if None in slots:
                slot_idx = slots.index(None)
                slots[slot_idx] = ref
                ref_bits[slot_idx] = 1
                evicted = None
                # hand stays or moves past placed slot
            else:
                # Cycle hand looking for ref_bit == 0
                while ref_bits[hand] == 1:
                    ref_bits[hand] = 0
                    hand = (hand + 1) % capacity
                evicted = slots[hand]
                slots[hand] = ref
                ref_bits[hand] = 1
                hand = (hand + 1) % capacity

        current_occupied = [s for s in slots if s is not None]
        step = CacheStep(
            step=idx,
            reference=ref,
            hit=hit,
            evicted=evicted,
            slots=current_occupied,
            extra={"hand": hand, "ref_bits": list(ref_bits)},
        )
        steps.append(step)

        trace.append(
            TraceStep(
                step=idx,
                skill="cache_replacement",
                algorithm="Clock",
                package="core.algorithms.caching",
                input={
                    "time": idx,
                    "reference": ref,
                    "slots": prev_occupied,
                    "hand": initial_hand,
                    "capacity": capacity,
                },
                output={
                    "hit": hit,
                    "evicted": evicted,
                    "new_slots": current_occupied,
                    "hand": hand,
                },
            )
        )

    return CacheResult(
        algorithm="Clock",
        capacity=capacity,
        references=list(references),
        hits=hits,
        misses=misses,
        hit_rate=hits / len(references),
        steps=steps,
        trace=trace,
        metrics=_make_metrics(hits, misses),
    )


def opt(references: list[str], capacity: int) -> CacheResult:
    """Belady's Optimal (OPT) offline replacement algorithm."""
    _validate(references, capacity)
    if not references:
        return _empty_result("OPT", capacity)

    slots: list[str] = []
    steps: list[CacheStep] = []
    trace: list[TraceStep] = []
    hits = 0
    misses = 0
    n = len(references)

    for idx, ref in enumerate(references, start=1):
        prev_slots = list(slots)
        if ref in slots:
            hits += 1
            hit = True
            evicted = None
        else:
            misses += 1
            hit = False
            if len(slots) >= capacity:
                future = references[idx:]  # remaining references after current
                # For each slot item, find its next occurrence index
                next_use: dict[str, int] = {}
                for item in slots:
                    try:
                        next_use[item] = future.index(item)
                    except ValueError:
                        next_use[item] = n + 1  # Never used again

                # Evict item used furthest in the future (or never).
                # Tie-break: item name alphabetical
                victim = max(slots, key=lambda item: (next_use[item], -slots.index(item)))
                evicted = victim
                slots.remove(victim)
            else:
                evicted = None
            slots.append(ref)

        step = CacheStep(
            step=idx,
            reference=ref,
            hit=hit,
            evicted=evicted,
            slots=list(slots),
        )
        steps.append(step)

        trace.append(
            TraceStep(
                step=idx,
                skill="cache_replacement",
                algorithm="OPT",
                package="core.algorithms.caching",
                input={"time": idx, "reference": ref, "slots": prev_slots, "capacity": capacity},
                output={"hit": hit, "evicted": evicted, "new_slots": list(slots)},
            )
        )

    return CacheResult(
        algorithm="OPT",
        capacity=capacity,
        references=list(references),
        hits=hits,
        misses=misses,
        hit_rate=hits / len(references),
        steps=steps,
        trace=trace,
        metrics=_make_metrics(hits, misses),
    )


ALGORITHMS: dict[str, Callable[[list[str], int], CacheResult]] = {
    "fifo": fifo,
    "lru": lru,
    "lfu": lfu,
    "clock": clock,
    "opt": opt,
}

ALGORITHM_INFO = [
    {"name": "fifo", "label": "FIFO", "description": "First-In First-Out"},
    {"name": "lru", "label": "LRU", "description": "Least Recently Used"},
    {"name": "lfu", "label": "LFU", "description": "Least Frequently Used"},
    {"name": "clock", "label": "Clock", "description": "Second Chance / Clock Replacement"},
    {"name": "opt", "label": "OPT", "description": "Belady Optimal (Offline Benchmark)"},
]


def run_caching(algorithm: str, references: list[str], capacity: int) -> CacheResult:
    key = algorithm.lower().strip()
    if key not in ALGORITHMS:
        raise ValueError(
            f"unknown caching algorithm {algorithm!r}; available: {sorted(ALGORITHMS)}"
        )
    return ALGORITHMS[key](references, capacity)

