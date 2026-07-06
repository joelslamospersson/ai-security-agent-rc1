"""
Health models — subsystem health states for the Health Supervisor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Any


class HealthState(StrEnum):
    """Possible health states for a subsystem."""

    UNINITIALIZED = auto()
    INITIALIZING = auto()
    HEALTHY = auto()
    DEGRADED = auto()
    FAILED = auto()
    SHUTDOWN = auto()


@dataclass
class SubsystemHealth:
    """Health status of a single subsystem."""

    name: str = ""
    state: HealthState = HealthState.UNINITIALIZED
    last_check: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    message: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Complete health report for all subsystems."""

    subsystems: dict[str, SubsystemHealth] = field(default_factory=dict)
    overall: HealthState = HealthState.UNINITIALIZED
    healthy_count: int = 0
    degraded_count: int = 0
    failed_count: int = 0
    emergency_mode: bool = False


class WorkerStatus(StrEnum):
    """Status of a background worker."""

    RUNNING = auto()
    HUNG = auto()
    CRASHED = auto()
    STOPPED = auto()
    DEADLOCKED = auto()


@dataclass
class WorkerInfo:
    """Information about a background worker."""

    name: str = ""
    status: WorkerStatus = WorkerStatus.RUNNING
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    restart_count: int = 0
    max_restarts: int = 3
    error: str = ""
