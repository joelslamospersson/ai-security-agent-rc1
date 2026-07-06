"""
Harness metrics — collects timing and performance data during simulation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HarnessMetrics:
    """Collected metrics during a harness run."""

    startup_time: float = 0.0
    shutdown_time: float = 0.0
    detection_latencies: list[float] = field(default_factory=list)
    routing_latencies: list[float] = field(default_factory=list)
    notification_latencies: list[float] = field(default_factory=list)
    audit_latencies: list[float] = field(default_factory=list)
    heartbeat_latencies: list[float] = field(default_factory=list)
    cpu_percent: float = 0.0
    ram_mb: float = 0.0
    disk_mb: float = 0.0


class MetricsCollector:
    """Collects timing and resource metrics during simulation."""

    def __init__(self) -> None:
        self.metrics = HarnessMetrics()
        self._timers: dict[str, float] = {}

    def start_timer(self, name: str) -> None:
        self._timers[name] = time.monotonic()

    def stop_timer(self, name: str) -> float:
        elapsed = time.monotonic() - self._timers.pop(name, 0.0)
        return elapsed

    def record_latency(self, category: str, latency_ms: float) -> None:
        target = getattr(self.metrics, f"{category}_latencies", None)
        if target is not None:
            target.append(latency_ms)

    def to_dict(self) -> dict[str, Any]:
        m = self.metrics
        return {
            "startup_time_ms": round(m.startup_time * 1000, 2),
            "shutdown_time_ms": round(m.shutdown_time * 1000, 2),
            "detection_latency_avg_ms": round(self._avg(m.detection_latencies), 2),
            "routing_latency_avg_ms": round(self._avg(m.routing_latencies), 2),
            "notification_latency_avg_ms": round(self._avg(m.notification_latencies), 2),
            "audit_latency_avg_ms": round(self._avg(m.audit_latencies), 2),
            "heartbeat_latency_avg_ms": round(self._avg(m.heartbeat_latencies), 2),
        }

    @staticmethod
    def _avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0
