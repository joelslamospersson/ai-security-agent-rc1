"""
Package lifecycle — state machine with legal transitions.
"""

from __future__ import annotations

import structlog

from management_server.configsync.exceptions import InvalidTransitionError
from management_server.configsync.models import PackageState

logger = structlog.get_logger("configsync.lifecycle")

LEGAL_TRANSITIONS: set[tuple[PackageState, PackageState]] = {
    (PackageState.CREATED, PackageState.SIGNED),
    (PackageState.SIGNED, PackageState.PUBLISHED),
    (PackageState.PUBLISHED, PackageState.AVAILABLE),
    (PackageState.AVAILABLE, PackageState.SUPERSEDED),
    (PackageState.SUPERSEDED, PackageState.ARCHIVED),
    (PackageState.CREATED, PackageState.ARCHIVED),
    (PackageState.PUBLISHED, PackageState.ARCHIVED),
}


class PackageLifecycle:
    """Manages package lifecycle transitions."""

    @classmethod
    def is_legal(cls, from_state: PackageState, to_state: PackageState) -> bool:
        return (from_state, to_state) in LEGAL_TRANSITIONS

    @classmethod
    def validate(cls, from_state: PackageState, to_state: PackageState) -> None:
        if not cls.is_legal(from_state, to_state):
            raise InvalidTransitionError(from_state.value, to_state.value)

    @classmethod
    def legal_transitions_from(cls, state: PackageState) -> list[PackageState]:
        return [to for (f, to) in LEGAL_TRANSITIONS if f == state]

    @classmethod
    def get_audit_event_type(cls, from_state: PackageState, to_state: PackageState) -> str:
        event_map = {
            (PackageState.CREATED, PackageState.SIGNED): "package_signed",
            (PackageState.SIGNED, PackageState.PUBLISHED): "package_published",
            (PackageState.PUBLISHED, PackageState.AVAILABLE): "package_available",
            (PackageState.AVAILABLE, PackageState.SUPERSEDED): "package_superseded",
            (PackageState.SUPERSEDED, PackageState.ARCHIVED): "package_archived",
        }
        return event_map.get((from_state, to_state), f"package_{to_state.value}")
