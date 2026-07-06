"""
Threat models — ThreatAssessment, RiskLevel, RecommendedAction.

Input: SecurityIncident
Output: ThreatAssessment

No enforcement occurs here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _uid() -> str:
    return str(uuid.uuid4())


class RiskLevel(IntEnum):
    INFORMATIONAL = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class RecommendedAction(IntEnum):
    IGNORE = 0
    MONITOR = 1
    INCREASE_REPUTATION = 2
    TEMPORARY_BAN = 3
    PERMANENT_BAN = 4
    NOTIFY_ADMIN = 5


# Default thresholds for risk classification
RISK_THRESHOLDS = {
    RiskLevel.INFORMATIONAL: (0, 20),
    RiskLevel.LOW: (21, 40),
    RiskLevel.MEDIUM: (41, 60),
    RiskLevel.HIGH: (61, 80),
    RiskLevel.CRITICAL: (81, 100),
}


@dataclass(slots=True, frozen=True)
class ThreatAssessment:
    """Immutable result of threat assessment.

    Produced by the Threat Engine for each SecurityIncident.
    Contains scores, risk level, and recommended actions.
    No enforcement is performed here.
    """

    threat_id: str = field(default_factory=_uid)
    incident_id: str = ""
    correlation_id: str = ""
    timestamp: datetime = field(default_factory=_now)

    # Scores
    confidence: int = 0
    threat_score: int = 0
    severity: int = 0

    # Risk
    risk_level: RiskLevel = RiskLevel.INFORMATIONAL

    # Evidence
    matched_rules: tuple[str, ...] = ()
    attack_chain_ids: tuple[str, ...] = ()
    matched_stages: int = 0
    total_stages: int = 0

    # Action recommendation
    recommended_action: RecommendedAction = RecommendedAction.IGNORE
    action_reason: str = ""

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0 <= self.confidence <= 100):
            raise ValueError(f"Confidence must be 0-100, got {self.confidence}")
        if not (0 <= self.threat_score <= 100):
            raise ValueError(f"Threat score must be 0-100, got {self.threat_score}")
        if not (0 <= self.severity <= 10):
            raise ValueError(f"Severity must be 0-10, got {self.severity}")
