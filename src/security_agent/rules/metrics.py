"""Metrics collection for the Rule Engine."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock


@dataclass
class RuleMetricsSnapshot:
    rules_loaded: int = 0
    rules_evaluated: int = 0
    rules_matched: int = 0
    evaluation_errors: int = 0
    avg_evaluation_latency_ms: float = 0.0
    max_evaluation_latency_ms: float = 0.0


class RuleMetricsCollector:
    """Thread-safe metrics collector for the Rule Engine."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._rules_loaded = 0
        self._rules_evaluated = 0
        self._rules_matched = 0
        self._evaluation_errors = 0
        self._latencies: list[float] = []
        self._start_time = time.monotonic()

    def rules_loaded(self, count: int = 1) -> None:
        with self._lock:
            self._rules_loaded += count

    def rule_evaluated(self) -> None:
        with self._lock:
            self._rules_evaluated += 1

    def rule_matched(self) -> None:
        with self._lock:
            self._rules_matched += 1

    def evaluation_error(self) -> None:
        with self._lock:
            self._evaluation_errors += 1

    def record_latency(self, seconds: float) -> None:
        with self._lock:
            ms = seconds * 1000
            self._latencies.append(ms)
            if len(self._latencies) > 10000:
                self._latencies = self._latencies[-10000:]

    def snapshot(self) -> RuleMetricsSnapshot:
        with self._lock:
            avg = (
                sum(self._latencies) / len(self._latencies) if self._latencies else 0.0
            )
            mx = max(self._latencies) if self._latencies else 0.0
            return RuleMetricsSnapshot(
                rules_loaded=self._rules_loaded,
                rules_evaluated=self._rules_evaluated,
                rules_matched=self._rules_matched,
                evaluation_errors=self._evaluation_errors,
                avg_evaluation_latency_ms=avg,
                max_evaluation_latency_ms=mx,
            )
