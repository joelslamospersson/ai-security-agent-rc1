"""
Firewall models — FirewallOperation, OperationType, BackendCapabilities.

Operations define WHAT should happen. Backends define HOW.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _uid() -> str:
    return str(uuid.uuid4())


class OperationType(StrEnum):
    BAN = "ban"
    UNBAN = "unban"
    REFRESH = "refresh"
    SYNC = "sync"
    VERIFY = "verify"


@dataclass(slots=True, frozen=True)
class BackendCapabilities:
    """Capabilities of a firewall backend.

    All capabilities default to False.
    Backends declare what they support.
    """

    ipv4: bool = False
    ipv6: bool = False
    cidr: bool = False
    ipset: bool = False
    nftables_sets: bool = False
    temporary_bans: bool = False
    permanent_bans: bool = False
    synchronization: bool = False
    batch_operations: bool = False
    name: str = ""


@dataclass(slots=True, frozen=True)
class FirewallOperation:
    """Immutable firewall operation.

    Defines what firewall change should happen.
    Concrete backends implement how it happens.
    """

    operation_id: str = field(default_factory=_uid)
    timestamp: datetime = field(default_factory=_now)
    correlation_id: str = ""
    entity: str = ""
    entity_type: str = ""
    operation_type: OperationType = OperationType.BAN
    duration: int = 0
    expires_at: float = 0.0
    reason: str = ""
    evidence: str = ""
    backend_hint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
