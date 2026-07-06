"""
MonitorContext — injected into every monitor at creation time.

Monitors access all external resources exclusively through this context.
No monitor should access global state or import core subsystems directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import Logger
from typing import Any

from security_agent.event_bus import EventBus, Publisher


@dataclass
class MonitorContext:
    """Isolated context for a single monitor instance.

    Monitors receive this context at initialization and use it
    for all external interactions: publishing events, reading config,
    logging, and recording metrics.

    Fields:
        name:          Monitor name (unique identifier).
        settings:      Configuration dict for this monitor.
        event_bus:     Event Bus for publishing events.
        publisher:     Scoped Publisher that injects monitor name.
        logger:        Structured logger scoped to this monitor.
        metrics:       Metrics interface (set by manager).
        metadata:      Arbitrary key-value store for monitor state.
    """

    name: str = ""
    settings: dict[str, Any] = field(default_factory=dict)
    event_bus: EventBus | None = None
    publisher: Publisher | None = None
    logger: Logger | None = None
    metrics: Any = None  # MetricsCollector set by manager
    metadata: dict[str, Any] = field(default_factory=dict)
