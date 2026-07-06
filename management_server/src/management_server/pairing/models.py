"""
Pairing token state model and lifecycle.

UNUSED → ISSUED → PENDING → CONSUMED
                      ↓
                   EXPIRED / REVOKED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import ClassVar

import structlog

from management_server.pairing.exceptions import InvalidTransitionError

logger = structlog.get_logger("pairing.models")


class TokenState(StrEnum):
    """All possible pairing token states."""

    UNUSED = auto()
    ISSUED = auto()
    PENDING = auto()
    CONSUMED = auto()
    EXPIRED = auto()
    REVOKED = auto()

    def __repr__(self) -> str:
        return f"TokenState.{self.name}"


@dataclass
class PairingToken:
    """Immutable pairing token value object.

    Only the SHA-256 hash of the token is stored; the plaintext value
    is returned to the caller at generation time and never persisted.
    """

    id: str = ""
    token_hash: str = ""
    status: TokenState = TokenState.UNUSED
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    expires_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    consumed_at: datetime | None = None
    creator: str = "system"
    machine_uuid: str | None = None
    audit_reference: str = ""

    @property
    def is_expired(self) -> bool:
        return datetime.now(tz=UTC) > self.expires_at

    @property
    def is_consumed(self) -> bool:
        return self.status == TokenState.CONSUMED

    @property
    def is_revoked(self) -> bool:
        return self.status == TokenState.REVOKED


@dataclass
class TokenTransition:
    """A single pairing token state transition record."""

    from_state: TokenState
    to_state: TokenState
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    reason: str = ""
    triggered_by: str = "system"


@dataclass
class TransitionRule:
    """Defines a legal transition between token states."""

    from_state: TokenState
    to_state: TokenState
    description: str = ""


class TokenStateMachine:
    """Validates and tracks pairing token lifecycle transitions.

    Legal transitions:
        UNUSED → ISSUED       (token created)
        ISSUED → PENDING      (token claimed by agent)
        PENDING → CONSUMED    (token consumed during pairing)
        PENDING → EXPIRED     (TTL reached)
        PENDING → REVOKED     (admin revokes)
        UNUSED → EXPIRED      (token expired before use)
        UNUSED → REVOKED      (admin revokes unused token)
        ISSUED → EXPIRED      (token expired during issue)
        ISSUED → REVOKED      (admin revokes issued token)
    """

    _rules: ClassVar[list[TransitionRule]] = [
        TransitionRule(TokenState.UNUSED, TokenState.ISSUED, "Token generated and issued"),
        TransitionRule(TokenState.ISSUED, TokenState.PENDING, "Token claimed by agent"),
        TransitionRule(TokenState.PENDING, TokenState.CONSUMED, "Token consumed during pairing"),
        TransitionRule(TokenState.PENDING, TokenState.EXPIRED, "Token TTL reached"),
        TransitionRule(TokenState.PENDING, TokenState.REVOKED, "Admin revokes pending token"),
        TransitionRule(TokenState.UNUSED, TokenState.EXPIRED, "Token expired before use"),
        TransitionRule(TokenState.UNUSED, TokenState.REVOKED, "Admin revokes unused token"),
        TransitionRule(TokenState.ISSUED, TokenState.EXPIRED, "Token expired during issue"),
        TransitionRule(TokenState.ISSUED, TokenState.REVOKED, "Admin revokes issued token"),
    ]

    _transition_map: ClassVar[dict[tuple[TokenState, TokenState], TransitionRule]] = {
        (r.from_state, r.to_state): r for r in _rules
    }

    @classmethod
    def is_legal(cls, from_state: TokenState, to_state: TokenState) -> bool:
        """Check if a transition between two states is legal."""
        return (from_state, to_state) in cls._transition_map

    @classmethod
    def validate_transition(cls, from_state: TokenState, to_state: TokenState) -> None:
        """Validate a state transition. Raises InvalidTransitionError if illegal."""
        if not cls.is_legal(from_state, to_state):
            raise InvalidTransitionError(from_state.value, to_state.value)

    @classmethod
    def legal_transitions_from(cls, state: TokenState) -> list[TokenState]:
        """List all legal target states from a given state."""
        return [to for (f, to) in cls._transition_map if f == state]
