"""Metrics collection for the Firewall abstraction."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class FirewallMetricsSnapshot:
    operations_created: int = 0
    operations_completed: int = 0
    operations_failed: int = 0
    sync_requests: int = 0
    backend_failures: int = 0
    registered_backends: int = 0


class FirewallMetricsCollector:
    """Thread-safe metrics collector."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._created = 0
        self._completed = 0
        self._failed = 0
        self._sync = 0
        self._backend_failures = 0

    def operation_created(self) -> None:
        with self._lock:
            self._created += 1

    def operation_completed(self) -> None:
        with self._lock:
            self._completed += 1

    def operation_failed(self) -> None:
        with self._lock:
            self._failed += 1

    def sync_requested(self) -> None:
        with self._lock:
            self._sync += 1

    def backend_failure(self) -> None:
        with self._lock:
            self._backend_failures += 1

    def snapshot(self, registered: int = 0) -> FirewallMetricsSnapshot:
        with self._lock:
            return FirewallMetricsSnapshot(
                operations_created=self._created,
                operations_completed=self._completed,
                operations_failed=self._failed,
                sync_requests=self._sync,
                backend_failures=self._backend_failures,
                registered_backends=registered,
            )
