"""
Audit metrics — thread-safe counters for the Audit Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class AuditMetricsSnapshot:
    events_written: int = 0
    validation_failures: int = 0
    export_requests: int = 0
    hash_failures: int = 0
    retention_calculations: int = 0


class AuditMetricsCollector:
    """Thread-safe metrics collector for the Audit Engine."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._written = 0
        self._validation_failures = 0
        self._export_requests = 0
        self._hash_failures = 0
        self._retention_calculations = 0

    def event_written(self) -> None:
        with self._lock:
            self._written += 1

    def validation_failure(self) -> None:
        with self._lock:
            self._validation_failures += 1

    def export_requested(self) -> None:
        with self._lock:
            self._export_requests += 1

    def hash_failure(self) -> None:
        with self._lock:
            self._hash_failures += 1

    def retention_calculated(self) -> None:
        with self._lock:
            self._retention_calculations += 1

    def snapshot(self) -> AuditMetricsSnapshot:
        with self._lock:
            return AuditMetricsSnapshot(
                events_written=self._written,
                validation_failures=self._validation_failures,
                export_requests=self._export_requests,
                hash_failures=self._hash_failures,
                retention_calculations=self._retention_calculations,
            )
