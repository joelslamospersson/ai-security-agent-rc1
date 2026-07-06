"""Metrics collection for the Correlation Engine."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class CorrelationMetricsSnapshot:
    active_incidents: int = 0
    completed_incidents: int = 0
    expired_incidents: int = 0
    chains_started: int = 0
    chains_advanced: int = 0
    chains_completed: int = 0
    chains_expired: int = 0
    errors: int = 0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0


class CorrelationMetricsCollector:
    """Thread-safe metrics collector."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._active = 0
        self._completed = 0
        self._expired = 0
        self._started = 0
        self._advanced = 0
        self._chains_completed = 0
        self._chains_expired = 0
        self._errors = 0
        self._latencies: list[float] = []

    def chain_started(self) -> None:
        with self._lock:
            self._started += 1
            self._active += 1

    def chain_advanced(self) -> None:
        with self._lock:
            self._advanced += 1

    def chain_completed(self) -> None:
        with self._lock:
            self._chains_completed += 1
            self._active = max(0, self._active - 1)
            self._completed += 1

    def chain_expired(self) -> None:
        with self._lock:
            self._chains_expired += 1
            self._active = max(0, self._active - 1)
            self._expired += 1

    def error(self) -> None:
        with self._lock:
            self._errors += 1

    def record_latency(self, seconds: float) -> None:
        with self._lock:
            ms = seconds * 1000
            self._latencies.append(ms)
            if len(self._latencies) > 10000:
                self._latencies = self._latencies[-10000:]

    def snapshot(self) -> CorrelationMetricsSnapshot:
        with self._lock:
            avg = (
                sum(self._latencies) / len(self._latencies) if self._latencies else 0.0
            )
            mx = max(self._latencies) if self._latencies else 0.0
            return CorrelationMetricsSnapshot(
                active_incidents=self._active,
                completed_incidents=self._completed,
                expired_incidents=self._expired,
                chains_started=self._started,
                chains_advanced=self._advanced,
                chains_completed=self._chains_completed,
                chains_expired=self._chains_expired,
                errors=self._errors,
                avg_latency_ms=avg,
                max_latency_ms=mx,
            )
