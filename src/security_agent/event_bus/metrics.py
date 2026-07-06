"""
Metrics collection for the Event Bus.

Tracks publish/delivery counts, latencies, queue depths, and subscriber stats.
This module exposes interfaces that will integrate with the Metrics subsystem
introduced in a later phase.

Currently uses simple in-process counters and ring buffers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class BusMetricsSnapshot:
    """Snapshot of all bus metrics at a point in time."""

    total_published: int = 0
    total_delivered: int = 0
    total_failed: int = 0
    total_dropped: int = 0
    current_queue_depth: int = 0
    peak_queue_depth: int = 0
    queue_capacity: int = 0
    subscriber_count: int = 0
    publish_latency_ms: float = 0.0
    delivery_latency_ms: float = 0.0
    events_per_second: float = 0.0
    slow_subscriber_count: int = 0
    queue_names: list[str] = field(default_factory=list)


class BusMetricsCollector:
    """Collects metrics for the Event Bus.

    Thread-safe. Uses Lock for counter updates.
    Later phases will replace this with the centralized Metrics subsystem.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._total_published: int = 0
        self._total_delivered: int = 0
        self._total_failed: int = 0
        self._total_dropped: int = 0
        self._publish_times: list[float] = []
        self._delivery_times: list[float] = []
        self._peak_queue_depth: int = 0
        self._slow_subscriber_count: int = 0
        self._start_time: float = time.monotonic()

    def increment_published(self, count: int = 1) -> None:
        with self._lock:
            self._total_published += count

    def increment_delivered(self, count: int = 1) -> None:
        with self._lock:
            self._total_delivered += count

    def increment_failed(self, count: int = 1) -> None:
        with self._lock:
            self._total_failed += count

    def increment_dropped(self, count: int = 1) -> None:
        with self._lock:
            self._total_dropped += count

    def record_publish_latency(self, seconds: float) -> None:
        with self._lock:
            self._publish_times.append(seconds * 1000)  # Convert to ms
            if len(self._publish_times) > 1000:
                self._publish_times = self._publish_times[-1000:]

    def record_delivery_latency(self, seconds: float) -> None:
        with self._lock:
            self._delivery_times.append(seconds * 1000)
            if len(self._delivery_times) > 1000:
                self._delivery_times = self._delivery_times[-1000:]

    def update_peak_depth(self, depth: int) -> None:
        with self._lock:
            if depth > self._peak_queue_depth:
                self._peak_queue_depth = depth

    def increment_slow_subscriber(self) -> None:
        with self._lock:
            self._slow_subscriber_count += 1

    def snapshot(
        self,
        current_depth: int = 0,
        queue_capacity: int = 0,
        subscriber_count: int = 0,
        queue_names: list[str] | None = None,
    ) -> BusMetricsSnapshot:
        """Return a snapshot of current metrics."""
        with self._lock:
            elapsed = time.monotonic() - self._start_time
            eps = self._total_published / elapsed if elapsed > 0 else 0.0
            avg_pub = (
                sum(self._publish_times) / len(self._publish_times)
                if self._publish_times
                else 0.0
            )
            avg_del = (
                sum(self._delivery_times) / len(self._delivery_times)
                if self._delivery_times
                else 0.0
            )

            return BusMetricsSnapshot(
                total_published=self._total_published,
                total_delivered=self._total_delivered,
                total_failed=self._total_failed,
                total_dropped=self._total_dropped,
                current_queue_depth=current_depth,
                peak_queue_depth=self._peak_queue_depth,
                queue_capacity=queue_capacity,
                subscriber_count=subscriber_count,
                publish_latency_ms=avg_pub,
                delivery_latency_ms=avg_del,
                events_per_second=round(eps, 1),
                slow_subscriber_count=self._slow_subscriber_count,
                queue_names=queue_names or [],
            )
