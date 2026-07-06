"""
Heartbeat metrics — thread-safe counters for the heartbeat protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class HeartbeatMetricsSnapshot:
    """Snapshot of heartbeat metrics."""

    heartbeats_received: int = 0
    heartbeats_missed: int = 0
    protocol_errors: int = 0
    version_mismatches: int = 0
    capability_changes: int = 0
    average_latency_ms: float = 0.0
    online_machines: int = 0
    offline_machines: int = 0
    delayed_machines: int = 0


class HeartbeatMetricsCollector:
    """Thread-safe metrics collector for the heartbeat subsystem."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._received = 0
        self._missed = 0
        self._protocol_errors = 0
        self._version_mismatches = 0
        self._capability_changes = 0
        self._latencies: list[float] = []

    def heartbeat_received(self, latency_ms: float = 0.0) -> None:
        with self._lock:
            self._received += 1
            if latency_ms > 0:
                self._latencies.append(latency_ms)

    def heartbeat_missed(self) -> None:
        with self._lock:
            self._missed += 1

    def protocol_error(self) -> None:
        with self._lock:
            self._protocol_errors += 1

    def version_mismatch(self) -> None:
        with self._lock:
            self._version_mismatches += 1

    def capability_change(self) -> None:
        with self._lock:
            self._capability_changes += 1

    def snapshot(
        self, online: int = 0, offline: int = 0, delayed: int = 0
    ) -> HeartbeatMetricsSnapshot:
        with self._lock:
            avg_latency = 0.0
            if self._latencies:
                avg_latency = sum(self._latencies) / len(self._latencies)
            return HeartbeatMetricsSnapshot(
                heartbeats_received=self._received,
                heartbeats_missed=self._missed,
                protocol_errors=self._protocol_errors,
                version_mismatches=self._version_mismatches,
                capability_changes=self._capability_changes,
                average_latency_ms=round(avg_latency, 2),
                online_machines=online,
                offline_machines=offline,
                delayed_machines=delayed,
            )
