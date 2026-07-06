"""
Notification metrics — thread-safe counters for the Notification Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class NotificationMetricsSnapshot:
    notifications_created: int = 0
    notifications_queued: int = 0
    notifications_dispatched: int = 0
    formatter_latency_ms: float = 0.0
    queue_depth: int = 0
    delivery_attempts: int = 0
    skipped_notifications: int = 0


class NotificationMetricsCollector:
    """Thread-safe metrics collector for the Notification Engine."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._created = 0
        self._queued = 0
        self._dispatched = 0
        self._formatter_latencies: list[float] = []
        self._delivery_attempts = 0
        self._skipped = 0

    def notification_created(self) -> None:
        with self._lock:
            self._created += 1

    def notification_queued(self) -> None:
        with self._lock:
            self._queued += 1

    def notification_dispatched(self) -> None:
        with self._lock:
            self._dispatched += 1

    def formatter_latency(self, latency_ms: float) -> None:
        with self._lock:
            self._formatter_latencies.append(latency_ms)

    def delivery_attempt(self) -> None:
        with self._lock:
            self._delivery_attempts += 1

    def skipped(self) -> None:
        with self._lock:
            self._skipped += 1

    def snapshot(self, queue_depth: int = 0) -> NotificationMetricsSnapshot:
        with self._lock:
            avg_latency = 0.0
            if self._formatter_latencies:
                avg_latency = sum(self._formatter_latencies) / len(self._formatter_latencies)
            return NotificationMetricsSnapshot(
                notifications_created=self._created,
                notifications_queued=self._queued,
                notifications_dispatched=self._dispatched,
                formatter_latency_ms=round(avg_latency, 2),
                queue_depth=queue_depth,
                delivery_attempts=self._delivery_attempts,
                skipped_notifications=self._skipped,
            )
