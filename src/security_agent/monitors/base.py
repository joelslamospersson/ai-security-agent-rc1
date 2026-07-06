"""
Abstract Monitor interface.

Every monitor implements the Monitor ABC. The MonitorManager
interacts only through this interface.

Monitors never communicate with each other or with the pipeline directly.
They publish events exclusively through the Event Bus.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from security_agent.monitors.context import MonitorContext


class HealthState(IntEnum):
    """Health status reported by monitors."""

    HEALTHY = 0
    DEGRADED = 1
    FAILED = 2
    STOPPED = 3


@dataclass
class HealthReport:
    """Snapshot of a monitor's health at a point in time."""

    status: HealthState = HealthState.STOPPED
    last_heartbeat: float = 0.0
    uptime: float = 0.0
    last_error: str = ""
    error_count: int = 0
    events_published: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class Monitor(ABC):
    """Abstract base for all monitoring sources.

    Lifecycle:
        initialize(ctx)  → prepare resources
        start()          → begin producing events
        stop()           → stop producing events, release resources
        health()         → return current health report
        capabilities()   → return dict of supported features

    Monitors publish events through ctx.publisher.
    Monitors never access the Pipeline Engine, detectors, or other monitors.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._context: MonitorContext | None = None
        self._start_time: float = 0.0
        self._stop_time: float = 0.0
        self._health: HealthState = HealthState.STOPPED
        self._last_error: str = ""
        self._error_count: int = 0
        self._events_published: int = 0

    @property
    def name(self) -> str:
        """Unique monitor identifier."""
        return self._name

    @property
    def context(self) -> MonitorContext | None:
        """The MonitorContext assigned at initialization."""
        return self._context

    @abstractmethod
    async def initialize(self, ctx: MonitorContext) -> None:
        """Prepare the monitor for operation.

        Called once by the MonitorManager before start().
        Receives the MonitorContext with event bus, config, logger.

        Args:
            ctx: Isolated context for this monitor instance.
        """
        self._context = ctx
        self._health = HealthState.STOPPED

    @abstractmethod
    async def start(self) -> None:
        """Begin producing events.

        After this method returns, the monitor should be actively
        watching its source and publishing events via ctx.publisher.
        """
        self._start_time = time.monotonic()
        self._health = HealthState.HEALTHY
        self._last_error = ""

    @abstractmethod
    async def stop(self) -> None:
        """Stop producing events and release resources.

        After this method returns, the monitor should no longer
        publish events or hold resources.
        """
        self._stop_time = time.monotonic()
        self._health = HealthState.STOPPED

    def health(self) -> HealthReport:
        """Return current health report."""
        uptime = time.monotonic() - self._start_time if self._start_time > 0 else 0.0
        return HealthReport(
            status=self._health,
            last_heartbeat=time.monotonic(),
            uptime=uptime,
            last_error=self._last_error,
            error_count=self._error_count,
            events_published=self._events_published,
        )

    def capabilities(self) -> dict[str, Any]:
        """Return supported features as a dict.

        Override to advertise capabilities like:
            {"journald": True, "file_monitor": False, "docker": False}
        """
        return {}

    def _record_error(self, error: str) -> None:
        """Record an error for health tracking."""
        self._last_error = error
        self._error_count += 1
        self._health = HealthState.DEGRADED

    def _record_failure(self, error: str) -> None:
        """Record a failure (health -> FAILED)."""
        self._last_error = error
        self._error_count += 1
        self._health = HealthState.FAILED

    def _increment_events(self, count: int = 1) -> None:
        """Increment the published events counter."""
        self._events_published += count
