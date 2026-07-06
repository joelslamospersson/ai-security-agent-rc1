"""
Ban models — BanDecision, BanLevel, BanPolicy, ExemptionPolicy.

Ban decisions are made here but never enforced (no iptables, nftables, etc).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _uid() -> str:
    return str(uuid.uuid4())


class BanLevel(IntEnum):
    """Escalation levels with standard durations in seconds."""

    WARNING = 0
    BAN_30M = 1
    BAN_1H = 2
    BAN_3H = 3
    BAN_24H = 4
    BAN_2D = 5
    BAN_7D = 6
    PERMANENT = 7


BAN_DURATIONS: dict[BanLevel, int] = {
    BanLevel.WARNING: 0,
    BanLevel.BAN_30M: 1800,
    BanLevel.BAN_1H: 3600,
    BanLevel.BAN_3H: 10800,
    BanLevel.BAN_24H: 86400,
    BanLevel.BAN_2D: 172800,
    BanLevel.BAN_7D: 604800,
    BanLevel.PERMANENT: 0,
}


class BanAction(StrEnum):
    NO_ACTION = "no_action"
    WARNING = "warning"
    TEMPORARY_BAN = "temporary_ban"
    PERMANENT_BAN = "permanent_ban"
    WHITELIST_SKIP = "whitelist_skip"
    EXEMPTION_SKIP = "exemption_skip"


class BanPolicy(StrEnum):
    AGGRESSIVE = "aggressive"
    BALANCED = "balanced"
    CONSERVATIVE = "conservative"
    LEARNING = "learning"
    CUSTOM = "custom"


@dataclass(slots=True, frozen=True)
class BanDecision:
    """Immutable ban decision. Never executed by this engine."""

    decision_id: str = field(default_factory=_uid)
    timestamp: datetime = field(default_factory=_now)
    entity: str = ""
    entity_type: str = ""
    correlation_id: str = ""

    # Scoring inputs
    threat_score: int = 0
    confidence: int = 0
    reputation_score: int = 0

    # Ban decision
    action: BanAction = BanAction.NO_ACTION
    escalation_level: BanLevel = BanLevel.WARNING
    ban_duration: int = 0
    is_permanent: bool = False

    # History
    previous_ban_count: int = 0
    is_repeat_offender: bool = False

    # Explanation
    reason: str = ""
    evidence: str = ""
    recommended_firewall_action: str = ""

    # Policy used
    policy_used: str = "balanced"

    def __post_init__(self) -> None:
        if not (0 <= self.threat_score <= 100):
            raise ValueError(f"Threat score must be 0-100, got {self.threat_score}")
        if not (0 <= self.confidence <= 100):
            raise ValueError(f"Confidence must be 0-100, got {self.confidence}")
