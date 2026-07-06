"""
DetectionResult — immutable result produced by every detector.

A DetectionResult represents the output of analyzing a single event.
It contains scoring, evidence, and metadata but no enforcement decisions.
Detectors never perform ban decisions or reputation changes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _new_uuid() -> str:
    return str(uuid.uuid4())


@dataclass(slots=True, frozen=True)
class DetectionResult:
    """Immutable result of analyzing a single event.

    Detectors create and return these. The framework collects and forwards
    them. No detector enforces bans, changes reputation, or sends alerts.
    """

    # Identity
    detection_id: str = field(default_factory=_new_uuid)
    detector_id: str = ""
    detector_name: str = ""

    # Event linkage
    event_id: str = ""
    correlation_id: str = ""

    # Timing
    timestamp: datetime = field(default_factory=_now_utc)

    # Scoring (confidence 0-100, severity 0-10)
    confidence: int = 0
    severity: int = 0
    threat_score: int = 0

    # Evidence and explanation
    threat_type: str = ""
    evidence: str = ""
    matched_fields: dict[str, str] = field(default_factory=dict)

    # Metadata extends evidence without altering meaning
    metadata: dict[str, Any] = field(default_factory=dict)

    # Recommended action for the pipeline (informational only)
    # Valid values: "monitor", "alert", "block", "ignore", ""
    recommended_action: str = ""

    def __post_init__(self) -> None:
        if not (0 <= self.confidence <= 100):
            raise ValueError(f"Confidence must be 0-100, got {self.confidence}")
        if not (0 <= self.severity <= 10):
            raise ValueError(f"Severity must be 0-10, got {self.severity}")
        if not (0 <= self.threat_score <= 100):
            raise ValueError(f"Threat score must be 0-100, got {self.threat_score}")
