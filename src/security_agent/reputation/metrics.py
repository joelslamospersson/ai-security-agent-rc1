"""Metrics collection for the Reputation Engine."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class ReputationMetricsSnapshot:
    total_entities: int = 0
    avg_score: float = 0.0
    min_score: int = 0
    max_score: int = 0
    negative_count: int = 0
    positive_count: int = 0
    neutral_count: int = 0
    updates: int = 0
    lookups: int = 0
    decay_operations: int = 0


class ReputationMetricsCollector:
    """Thread-safe metrics collector."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._updates = 0
        self._lookups = 0
        self._decay_ops = 0

    def update(self) -> None:
        with self._lock:
            self._updates += 1

    def lookup(self) -> None:
        with self._lock:
            self._lookups += 1

    def decay(self) -> None:
        with self._lock:
            self._decay_ops += 1

    def snapshot(self, entities: list[Any]) -> ReputationMetricsSnapshot:
        with self._lock:
            scores = [e.current_score for e in entities]
            total = len(scores)
            avg = sum(scores) / total if total > 0 else 0.0
            mn = min(scores) if scores else 0
            mx = max(scores) if scores else 0
            neg = sum(1 for s in scores if s < 0)
            pos = sum(1 for s in scores if s > 0)
            neu = sum(1 for s in scores if s == 0)
            return ReputationMetricsSnapshot(
                total_entities=total,
                avg_score=avg,
                min_score=mn,
                max_score=mx,
                negative_count=neg,
                positive_count=pos,
                neutral_count=neu,
                updates=self._updates,
                lookups=self._lookups,
                decay_operations=self._decay_ops,
            )
