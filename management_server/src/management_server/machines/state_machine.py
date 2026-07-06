"""
Machine state machine — legal transitions, validation, and audit trail.

States:
    UNKNOWN → PENDING_REGISTRATION → REGISTERED → ONLINE → DEGRADED/OFFLINE
    PENDING_REGISTRATION → REJECTED/EXPIRED
    REGISTERED/ONLINE/DEGRADED/OFFLINE → QUARANTINED → REVOKED

This phase implements only registration-related transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import ClassVar

import structlog

from management_server.machines.exceptions import InvalidTransitionError

logger = structlog.get_logger("machines.state_machine")


class MachineState(StrEnum):
    """All possible machine states."""

    UNKNOWN = auto()
    PENDING_REGISTRATION = auto()
    REGISTERED = auto()
    ONLINE = auto()
    DEGRADED = auto()
    OFFLINE = auto()
    QUARANTINED = auto()
    REJECTED = auto()
    EXPIRED = auto()
    REVOKED = auto()

    def __repr__(self) -> str:
        return f"MachineState.{self.name}"


@dataclass
class Transition:
    """A single state transition record."""

    from_state: MachineState
    to_state: MachineState
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    reason: str = ""
    triggered_by: str = "system"  # system, admin, machine


@dataclass
class TransitionRule:
    """Defines a legal transition between states."""

    from_state: MachineState
    to_state: MachineState
    requires_approval: bool = False
    description: str = ""


class MachineStateMachine:
    """Validates and tracks machine state transitions.

    Legal transitions (Phase 4 scope: registration only):

        UNKNOWN → PENDING_REGISTRATION    (new machine requests registration)
        PENDING_REGISTRATION → REGISTERED (admin approves)
        PENDING_REGISTRATION → REJECTED   (admin rejects)
        PENDING_REGISTRATION → EXPIRED    (registration TTL reached)
        REGISTERED → QUARANTINED          (admin or policy)
        REGISTERED → REVOKED              (admin revokes trust)

    Future phases add ONLINE/DEGRADED/OFFLINE and other transitions.
    """

    _rules: ClassVar[list[TransitionRule]] = [
        TransitionRule(
            MachineState.UNKNOWN,
            MachineState.PENDING_REGISTRATION,
            description="New machine registration request",
        ),
        TransitionRule(
            MachineState.PENDING_REGISTRATION,
            MachineState.REGISTERED,
            requires_approval=True,
            description="Admin approval",
        ),
        TransitionRule(
            MachineState.PENDING_REGISTRATION, MachineState.REJECTED, description="Admin rejection"
        ),
        TransitionRule(
            MachineState.PENDING_REGISTRATION,
            MachineState.EXPIRED,
            description="Registration TTL expired",
        ),
        TransitionRule(
            MachineState.REGISTERED,
            MachineState.QUARANTINED,
            description="Admin or policy quarantine",
        ),
        TransitionRule(
            MachineState.REGISTERED, MachineState.REVOKED, description="Admin revokes trust"
        ),
        TransitionRule(
            MachineState.QUARANTINED,
            MachineState.REVOKED,
            description="Admin revokes after quarantine",
        ),
        # Future phases add more transitions here
    ]

    _transition_map: ClassVar[dict[tuple[MachineState, MachineState], TransitionRule]] = {
        (r.from_state, r.to_state): r for r in _rules
    }

    def __init__(self) -> None:
        self._history: list[Transition] = []

    @classmethod
    def is_legal(cls, from_state: MachineState, to_state: MachineState) -> bool:
        """Check if a transition between two states is legal."""
        return (from_state, to_state) in cls._transition_map

    @classmethod
    def get_rule(cls, from_state: MachineState, to_state: MachineState) -> TransitionRule | None:
        """Get the transition rule, if any."""
        return cls._transition_map.get((from_state, to_state))

    @classmethod
    def legal_transitions_from(cls, state: MachineState) -> list[MachineState]:
        """List all legal target states from a given state."""
        return [to for (f, to) in cls._transition_map if f == state]

    @classmethod
    def validate_transition(cls, from_state: MachineState, to_state: MachineState) -> None:
        """Validate a state transition. Raises InvalidTransitionError if illegal."""
        if not cls.is_legal(from_state, to_state):
            raise InvalidTransitionError(from_state.value, to_state.value)

    def apply(
        self,
        from_state: MachineState,
        to_state: MachineState,
        reason: str = "",
        triggered_by: str = "system",
    ) -> Transition:
        """Apply a transition and record it in history."""
        self.validate_transition(from_state, to_state)
        transition = Transition(
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            triggered_by=triggered_by,
        )
        self._history.append(transition)
        logger.info(
            "State transition",
            from_state=from_state.value,
            to_state=to_state.value,
            reason=reason,
            triggered_by=triggered_by,
        )
        return transition

    @property
    def history(self) -> list[Transition]:
        """Get the full transition history."""
        return list(self._history)

    @property
    def history_count(self) -> int:
        return len(self._history)

    @classmethod
    def all_states(cls) -> list[MachineState]:
        """Return all defined states."""
        return list(MachineState)

    @classmethod
    def registration_states(cls) -> list[MachineState]:
        """Return states relevant to the registration workflow."""
        return [
            MachineState.UNKNOWN,
            MachineState.PENDING_REGISTRATION,
            MachineState.REGISTERED,
            MachineState.REJECTED,
            MachineState.EXPIRED,
        ]
