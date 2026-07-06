"""
Machine registry metrics — thread-safe counters for monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class RegistryMetricsSnapshot:
    """Snapshot of registry metrics."""

    registrations_requested: int = 0
    approved: int = 0
    rejected: int = 0
    expired: int = 0
    revoked: int = 0
    pending: int = 0
    total_machines: int = 0
    average_approval_time_ms: float = 0.0


class RegistryMetricsCollector:
    """Thread-safe metrics collector for the machine registry."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requested = 0
        self._approved = 0
        self._rejected = 0
        self._expired = 0
        self._revoked = 0
        self._approval_times: list[float] = []

    def registration_requested(self) -> None:
        with self._lock:
            self._requested += 1

    def approved(self, approval_time_seconds: float = 0.0) -> None:
        with self._lock:
            self._approved += 1
            if approval_time_seconds > 0:
                self._approval_times.append(approval_time_seconds)

    def rejected(self) -> None:
        with self._lock:
            self._rejected += 1

    def expired(self) -> None:
        with self._lock:
            self._expired += 1

    def revoked(self) -> None:
        with self._lock:
            self._revoked += 1

    def snapshot(self, pending: int = 0, total_machines: int = 0) -> RegistryMetricsSnapshot:
        with self._lock:
            avg_ms = 0.0
            if self._approval_times:
                avg_ms = (sum(self._approval_times) / len(self._approval_times)) * 1000.0
            return RegistryMetricsSnapshot(
                registrations_requested=self._requested,
                approved=self._approved,
                rejected=self._rejected,
                expired=self._expired,
                revoked=self._revoked,
                pending=pending,
                total_machines=total_machines,
                average_approval_time_ms=round(avg_ms, 2),
            )
