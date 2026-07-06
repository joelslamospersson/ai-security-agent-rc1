"""
Monitor-specific lifecycle events.

These are published on the Event Bus to inform other subsystems
about monitor state changes. They are NOT log-parsing events.
"""

from __future__ import annotations

from typing import Any

from security_agent.events import EventCategory, EventType, InternalEvent, Priority


def _monitor_event(
    internal_type: str,
    monitor_name: str,
    priority: Priority = Priority.NORMAL,
    **extra: Any,
) -> InternalEvent:
    """Create a monitor lifecycle InternalEvent."""
    data: dict[str, Any] = {"monitor": monitor_name}
    data.update(extra)
    return InternalEvent(
        event_type=EventType.INTERNAL_METRICS,
        category=EventCategory.PLUGIN,
        priority=priority,
        source=f"monitor.{monitor_name}",
        internal_type=internal_type,
        data=data,
    )


def monitor_started(monitor_name: str) -> InternalEvent:
    """Published when a monitor starts successfully."""
    return _monitor_event("monitor.started", monitor_name)


def monitor_stopped(monitor_name: str) -> InternalEvent:
    """Published when a monitor stops cleanly."""
    return _monitor_event("monitor.stopped", monitor_name)


def monitor_failed(monitor_name: str, error: str) -> InternalEvent:
    """Published when a monitor encounters a failure."""
    return _monitor_event(
        "monitor.failed",
        monitor_name,
        priority=Priority.HIGH,
        error=error,
    )


def monitor_health_changed(
    monitor_name: str,
    old_status: str,
    new_status: str,
) -> InternalEvent:
    """Published when a monitor's health status changes."""
    return _monitor_event(
        "monitor.health_changed",
        monitor_name,
        old_status=old_status,
        new_status=new_status,
    )
