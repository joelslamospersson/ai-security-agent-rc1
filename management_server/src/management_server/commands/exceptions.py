"""
Command exceptions — typed error hierarchy for the Remote Command Framework.
"""

from __future__ import annotations


class CommandError(Exception):
    """Base exception for all command-related errors."""


class InvalidTransitionError(CommandError):
    """Illegal command lifecycle transition."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition from {current} to {target}")


class CommandNotFoundError(CommandError):
    """Command not found."""

    def __init__(self, command_id: str) -> None:
        super().__init__(f"Command not found: {command_id}")


class CommandValidationError(CommandError):
    """Command validation failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class AuthorizationError(CommandError):
    """Command authorization failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class UnsupportedCommandTypeError(CommandError):
    """Unknown or unsupported command type."""

    def __init__(self, command_type: str) -> None:
        super().__init__(f"Unsupported command type: {command_type}")


class CommandExpiredError(CommandError):
    """Command has expired."""

    def __init__(self, command_id: str) -> None:
        super().__init__(f"Command expired: {command_id}")


class QueueError(CommandError):
    """Command queue error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class CommandRepositoryError(CommandError):
    """Database error during command operations."""
