"""
Immutable event models for the Event Bus.

Every event is a frozen dataclass. Once created, events cannot be modified.

Event hierarchy:
    BaseEvent (abstract foundation)
    ├── SecurityEvent
    ├── SystemEvent
    ├── HealthEvent
    ├── AlertEvent
    ├── LifecycleEvent
    ├── ConfigurationEvent
    └── InternalEvent
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from security_agent.events.event_types import EventCategory, EventType
from security_agent.events.priority import DEFAULT_PRIORITY, Priority


def _now_utc() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(tz=UTC)


def _new_uuid() -> str:
    """Generate a new UUID v4 string."""
    return str(uuid.uuid4())


# =========================================================================
# Base Event
# =========================================================================


@dataclass(slots=True, frozen=True)
class BaseEvent:
    """Foundation for all events flowing through the Event Bus.

    Every event carries:
    - Unique event_id (UUID v4)
    - correlation_id for tracing event chains
    - UTC timestamp at creation
    - Event type and category for routing
    - Priority for queue ordering
    - Severity (0-10)
    - Source component name
    - Arbitrary metadata dict
    - Typed payload
    """

    event_id: str = field(default_factory=_new_uuid)
    correlation_id: str = field(default_factory=_new_uuid)
    timestamp: datetime = field(default_factory=_now_utc)
    event_type: EventType = EventType.INTERNAL_METRICS
    category: EventCategory = EventCategory.INTERNAL
    priority: Priority = DEFAULT_PRIORITY
    severity: int = 0
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    payload: Any = None

    def __post_init__(self) -> None:
        """Validate severity range."""
        if not (0 <= self.severity <= 10):
            raise ValueError(f"Severity must be 0-10, got {self.severity}")


# =========================================================================
# Specific Event Types
# =========================================================================


@dataclass(slots=True, frozen=True)
class SecurityEvent(BaseEvent):
    """A security-relevant event (detection, threat, etc.)."""

    event_type: EventType = EventType.SECURITY_EVENT
    category: EventCategory = EventCategory.SECURITY
    priority: Priority = Priority.HIGH

    # Security-specific fields
    source_ip: str | None = None
    dest_ip: str | None = None
    source_port: int | None = None
    dest_port: int | None = None
    protocol: str | None = None
    username: str | None = None
    raw_message: str = ""
    threat_score: int = 0
    confidence: int = 0


@dataclass(slots=True, frozen=True)
class SystemEvent(BaseEvent):
    """System-level event (service state, resource usage, etc.)."""

    event_type: EventType = EventType.MONITOR_STARTED
    category: EventCategory = EventCategory.MONITORING
    priority: Priority = Priority.NORMAL

    process_name: str | None = None
    pid: int | None = None
    service_name: str | None = None
    exit_code: int | None = None


@dataclass(slots=True, frozen=True)
class HealthEvent(BaseEvent):
    """Agent self-monitoring health event."""

    event_type: EventType = EventType.HEALTH_CHECK
    category: EventCategory = EventCategory.HEALTH
    priority: Priority = Priority.HIGH

    check_name: str = ""
    status: str = "ok"  # "ok", "warning", "critical"
    value: float = 0.0
    threshold: float = 0.0
    message: str = ""


@dataclass(slots=True, frozen=True)
class AlertEvent(BaseEvent):
    """An alert that should be delivered via alert channels."""

    event_type: EventType = EventType.ALERT_TRIGGERED
    category: EventCategory = EventCategory.ALERT
    priority: Priority = Priority.HIGH

    title: str = ""
    message: str = ""
    channel: str = "info"  # "info", "warning", "critical", "security", "system", "bans"
    source_ip: str | None = None
    threat_type: str | None = None
    confidence: int = 0
    ban_action: str | None = None


@dataclass(slots=True, frozen=True)
class LifecycleEvent(BaseEvent):
    """Application or component lifecycle event."""

    event_type: EventType = EventType.APPLICATION_STARTING
    category: EventCategory = EventCategory.LIFECYCLE
    priority: Priority = Priority.CRITICAL

    component_name: str = ""
    component_version: str = ""
    transition: str = ""  # "starting", "started", "stopping", "stopped", "failed"


@dataclass(slots=True, frozen=True)
class ConfigurationEvent(BaseEvent):
    """Configuration change event."""

    event_type: EventType = EventType.CONFIG_CHANGED
    category: EventCategory = EventCategory.CONFIGURATION
    priority: Priority = Priority.NORMAL

    config_key: str = ""
    old_value: Any = None
    new_value: Any = None
    change_source: str = ""


@dataclass(slots=True, frozen=True)
class InternalEvent(BaseEvent):
    """Internal bus event (metrics, backpressure, etc.)."""

    event_type: EventType = EventType.INTERNAL_METRICS
    category: EventCategory = EventCategory.INTERNAL
    priority: Priority = Priority.LOW

    internal_type: str = ""
    data: dict[str, Any] = field(default_factory=dict)
