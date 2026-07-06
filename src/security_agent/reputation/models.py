"""
Reputation models — ReputationRecord, EntityType.

Reputation is long-term security memory. No enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EntityType(StrEnum):
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    CIDR = "cidr"
    USERNAME = "username"
    HOSTNAME = "hostname"
    ASN = "asn"
    COUNTRY = "country"
    PROCESS = "process"
    CONTAINER_ID = "container_id"
    SESSION_ID = "session_id"


REPUTATION_MIN = -100
REPUTATION_MAX = 100
REPUTATION_DEFAULT = 0


@dataclass(slots=True, frozen=True)
class ReputationRecord:
    """Immutable reputation record for a single entity.

    Scores range from REPUTATION_MIN (-100) to REPUTATION_MAX (+100).
    New entities start at 0 (unknown).
    """

    entity_type: EntityType = EntityType.IPV4
    entity_value: str = ""
    current_score: int = REPUTATION_DEFAULT
    previous_score: int = REPUTATION_DEFAULT
    confidence: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0
    event_count: int = 0
    ban_count: int = 0
    decay_state: str = "active"  # "active", "decayed", "permanent"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (REPUTATION_MIN <= self.current_score <= REPUTATION_MAX):
            raise ValueError(
                f"Score must be {REPUTATION_MIN}-{REPUTATION_MAX}, "
                f"got {self.current_score}"
            )
