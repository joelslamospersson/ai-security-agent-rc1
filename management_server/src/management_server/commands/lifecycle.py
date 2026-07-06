"""
Command lifecycle — state machine with legal transitions and audit emission.
"""

from __future__ import annotations

from typing import ClassVar

import structlog

from management_server.commands.exceptions import InvalidTransitionError
from management_server.commands.models import CommandState

logger = structlog.get_logger("commands.lifecycle")

# Legal transitions: (from_state, to_state) pairs
LEGAL_TRANSITIONS: set[tuple[CommandState, CommandState]] = {
    (CommandState.CREATED, CommandState.QUEUED),
    (CommandState.QUEUED, CommandState.AUTHORIZED),
    (CommandState.QUEUED, CommandState.CANCELLED),
    (CommandState.QUEUED, CommandState.EXPIRED),
    (CommandState.AUTHORIZED, CommandState.READY),
    (CommandState.AUTHORIZED, CommandState.CANCELLED),
    (CommandState.READY, CommandState.DELIVERED),
    (CommandState.READY, CommandState.CANCELLED),
    (CommandState.READY, CommandState.EXPIRED),
    (CommandState.DELIVERED, CommandState.ACKNOWLEDGED),
    (CommandState.ACKNOWLEDGED, CommandState.RUNNING),
    (CommandState.RUNNING, CommandState.SUCCESS),
    (CommandState.RUNNING, CommandState.FAILED),
    (CommandState.CREATED, CommandState.CANCELLED),
    (CommandState.CREATED, CommandState.EXPIRED),
}


class CommandLifecycle:
    """Manages command lifecycle transitions with validation."""

    TRANSITIONS: ClassVar[set[tuple[CommandState, CommandState]]] = LEGAL_TRANSITIONS

    @classmethod
    def is_legal(cls, from_state: CommandState, to_state: CommandState) -> bool:
        """Check if a transition is legal."""
        return (from_state, to_state) in cls.TRANSITIONS

    @classmethod
    def validate(cls, from_state: CommandState, to_state: CommandState) -> None:
        """Validate a transition. Raises InvalidTransitionError if illegal."""
        if not cls.is_legal(from_state, to_state):
            raise InvalidTransitionError(from_state.value, to_state.value)

    @classmethod
    def legal_transitions_from(cls, state: CommandState) -> list[CommandState]:
        """List all legal target states from a given state."""
        return [to for (f, to) in cls.TRANSITIONS if f == state]

    @classmethod
    def can_cancel(cls, state: CommandState) -> bool:
        """Check if a command can be cancelled from this state."""
        return cls.is_legal(state, CommandState.CANCELLED)

    @classmethod
    def can_expire(cls, state: CommandState) -> bool:
        """Check if a command can expire from this state."""
        return cls.is_legal(state, CommandState.EXPIRED)

    @classmethod
    def get_audit_event_type(cls, from_state: CommandState, to_state: CommandState) -> str:
        """Get the audit event type for a transition."""
        event_map: dict[tuple[CommandState, CommandState], str] = {
            (CommandState.CREATED, CommandState.QUEUED): "command_queued",
            (CommandState.QUEUED, CommandState.AUTHORIZED): "command_authorized",
            (CommandState.QUEUED, CommandState.CANCELLED): "command_cancelled",
            (CommandState.QUEUED, CommandState.EXPIRED): "command_expired",
            (CommandState.AUTHORIZED, CommandState.READY): "command_ready",
            (CommandState.READY, CommandState.DELIVERED): "command_delivered",
            (CommandState.DELIVERED, CommandState.ACKNOWLEDGED): "command_acknowledged",
            (CommandState.RUNNING, CommandState.SUCCESS): "command_success",
            (CommandState.RUNNING, CommandState.FAILED): "command_failed",
            (CommandState.CREATED, CommandState.CANCELLED): "command_cancelled",
            (CommandState.CREATED, CommandState.EXPIRED): "command_expired",
        }
        return event_map.get((from_state, to_state), f"command_{to_state.value}")
