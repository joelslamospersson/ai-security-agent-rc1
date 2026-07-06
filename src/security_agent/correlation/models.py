"""
Correlation data models — AttackChain, ChainStage, SecurityIncident, CorrelationKey.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _uid() -> str:
    return str(uuid.uuid4())


class StageType(StrEnum):
    ORDERED = "ordered"
    OPTIONAL = "optional"
    UNORDERED = "unordered"
    BRANCH = "branch"


class IncidentState(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"


class CorrelationKey(StrEnum):
    """Keys used to group related RuleMatches into incidents."""

    SOURCE_IP = "source_ip"
    DEST_IP = "dest_ip"
    USERNAME = "username"
    HOSTNAME = "hostname"
    CORRELATION_ID = "correlation_id"
    PROCESS = "process"
    SESSION = "session"
    CONTAINER_ID = "container_id"


@dataclass(slots=True, frozen=True)
class ChainStage:
    """A single stage in an attack chain."""

    stage_id: str = ""
    stage_type: StageType = StageType.ORDERED
    rule_ids: tuple[str, ...] = ()
    timeout: int = 300  # seconds
    confidence_modifier: int = 0
    description: str = ""


@dataclass(slots=True, frozen=True)
class AttackChain:
    """An attack chain definition loaded from YAML."""

    id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0"
    enabled: bool = True
    correlation_key: CorrelationKey = CorrelationKey.SOURCE_IP
    timeout: int = 3600  # seconds for entire chain
    stages: tuple[ChainStage, ...] = ()
    confidence_modifier: int = 0
    severity: int = 0
    threat_score: int = 0


@dataclass
class StageProgress:
    """Mutable progress tracking for a single stage."""

    stage_id: str = ""
    matched: bool = False
    matched_at: float = 0.0
    matched_rules: list[str] = field(default_factory=list)
    matched_events: list[str] = field(default_factory=list)


@dataclass
class ActiveChain:
    """Mutable state for an in-progress attack chain."""

    incident_id: str = field(default_factory=_uid)
    chain_id: str = ""
    correlation_key: str = ""
    key_value: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    last_match_at: float = 0.0
    stage_progress: dict[str, StageProgress] = field(default_factory=dict)
    current_stage_index: int = 0
    completed: bool = False
    expired: bool = False
    confidence: int = 0

    def is_expired(self, timeout: int, now: float) -> bool:
        return (now - self.last_match_at) > timeout


@dataclass(slots=True, frozen=True)
class SecurityIncident:
    """Immutable incident produced when an attack chain completes."""

    incident_id: str = ""
    attack_chain_id: str = ""
    correlation_id: str = ""
    created_at: datetime = field(default_factory=_now)
    state: IncidentState = IncidentState.ACTIVE
    matched_rules: tuple[str, ...] = ()
    matched_events: tuple[str, ...] = ()
    progress: int = 0
    confidence_modifier: int = 0
    evidence: str = ""
