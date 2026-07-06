"""
Routing metrics — thread-safe counters for the Routing Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class RoutingMetricsSnapshot:
    routing_decisions: int = 0
    rule_matches: int = 0
    default_route_usage: int = 0
    validation_failures: int = 0
    evaluation_latency_ms: float = 0.0


class RoutingMetricsCollector:
    """Thread-safe metrics collector for the Routing Engine."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._decisions = 0
        self._rule_matches = 0
        self._default_usage = 0
        self._validation_failures = 0
        self._latencies: list[float] = []

    def decision_created(self, latency_ms: float = 0.0) -> None:
        with self._lock:
            self._decisions += 1
            if latency_ms > 0:
                self._latencies.append(latency_ms)

    def rule_matched(self) -> None:
        with self._lock:
            self._rule_matches += 1

    def default_route_used(self) -> None:
        with self._lock:
            self._default_usage += 1

    def validation_failure(self) -> None:
        with self._lock:
            self._validation_failures += 1

    def snapshot(self) -> RoutingMetricsSnapshot:
        with self._lock:
            avg_latency = 0.0
            if self._latencies:
                avg_latency = sum(self._latencies) / len(self._latencies)
            return RoutingMetricsSnapshot(
                routing_decisions=self._decisions,
                rule_matches=self._rule_matches,
                default_route_usage=self._default_usage,
                validation_failures=self._validation_failures,
                evaluation_latency_ms=round(avg_latency, 2),
            )
