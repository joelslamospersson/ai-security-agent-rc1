"""
Machine registration exceptions — typed error hierarchy.
"""

from __future__ import annotations


class MachineError(Exception):
    """Base exception for all machine-related errors."""


class RegistrationError(MachineError):
    """Registration workflow error."""


class InvalidTransitionError(MachineError):
    """Attempted an illegal state transition."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition from {current} to {target}")


class DuplicateMachineError(MachineError):
    """Machine already exists in the registry."""

    def __init__(self, machine_uuid: str) -> None:
        self.machine_uuid = machine_uuid
        super().__init__(f"Machine {machine_uuid} already registered")


class ApprovalError(MachineError):
    """Approval workflow error."""


class MachineNotFoundError(MachineError):
    """Machine not found in the registry."""

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"Machine not found: {identifier}")


class StateMachineError(MachineError):
    """State machine configuration or validation error."""


class RepositoryError(MachineError):
    """Database repository error."""
