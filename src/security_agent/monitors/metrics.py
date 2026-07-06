"""
Metrics collection for the Monitor Framework.

Tracks monitor lifecycle, health transitions, and event publishing rates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class MonitorMetricsSnapshot:
    """Snapshot of monitor framework metrics."""

    running_monitors: int = 0
    failed_monitors: int = 0
    total_restarts: int = 0
    total_events_published: int = 0
    health_transitions: int = 0
    total_errors: int = 0
    startup_time_ms: float = 0.0
    shutdown_time_ms: float = 0.0
    registered_monitors: int = 0
    enabled_monitors: int = 0
    disabled_monitors: int = 0
    monitor_names: list[str] = field(default_factory=list)


class MonitorMetricsCollector:
    """Collects metrics for the Monitor Framework.

    Thread-safe. Uses Lock for counter updates.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._running_monitors: int = 0
        self._failed_monitors: int = 0
        self._total_restarts: int = 0
        self._total_events: int = 0
        self._health_transitions: int = 0
        self._total_errors: int = 0
        self._startup_time: float = 0.0
        self._shutdown_time: float = 0.0

    def monitor_started(self) -> None:
        with self._lock:
            self._running_monitors += 1

    def monitor_stopped(self) -> None:
        with self._lock:
            self._running_monitors = max(0, self._running_monitors - 1)

    def monitor_failed(self) -> None:
        with self._lock:
            self._failed_monitors += 1
            self._total_errors += 1

    def monitor_restarted(self) -> None:
        with self._lock:
            self._total_restarts += 1

    def events_published(self, count: int = 1) -> None:
        with self._lock:
            self._total_events += count

    def health_transition(self) -> None:
        with self._lock:
            self._health_transitions += 1

    def record_error(self) -> None:
        with self._lock:
            self._total_errors += 1

    def record_startup_time(self, seconds: float) -> None:
        with self._lock:
            self._startup_time = seconds * 1000

    def record_shutdown_time(self, seconds: float) -> None:
        with self._lock:
            self._shutdown_time = seconds * 1000

    def snapshot(
        self,
        registered: int = 0,
        enabled: int = 0,
        disabled: int = 0,
        names: list[str] | None = None,
    ) -> MonitorMetricsSnapshot:
        with self._lock:
            return MonitorMetricsSnapshot(
                running_monitors=self._running_monitors,
                failed_monitors=self._failed_monitors,
                total_restarts=self._total_restarts,
                total_events_published=self._total_events,
                health_transitions=self._health_transitions,
                total_errors=self._total_errors,
                startup_time_ms=self._startup_time,
                shutdown_time_ms=self._shutdown_time,
                registered_monitors=registered,
                enabled_monitors=enabled,
                disabled_monitors=disabled,
                monitor_names=names or [],
            )
