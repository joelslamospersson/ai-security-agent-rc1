"""
DetectorContext — immutable context passed to every detector.

Detectors receive this context at analysis time. It provides access
to configuration, logging, and metadata without exposing global state
or core subsystems (firewall, database, reputation, alerts).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import Logger
from typing import Any


@dataclass(frozen=True)
class DetectorContext:
    """Immutable context for a single analysis call.

    Detectors receive a fresh context for each event analysis.
    The context provides everything a detector needs to make a decision
    but nothing it could use to bypass security controls.

    Fields:
        settings:       Detector-specific configuration dict.
        logger:         Structured logger scoped to this detector.
        event_metadata: Metadata from the event being analyzed.
        correlation_id: Correlation ID for the current event chain.
        shared:         Framework-provided utilities (read-only).
    """

    settings: dict[str, Any] = field(default_factory=dict)
    logger: Logger | None = None
    event_metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    shared: dict[str, Any] = field(default_factory=dict)
