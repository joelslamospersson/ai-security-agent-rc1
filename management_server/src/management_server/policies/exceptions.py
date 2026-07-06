"""
Policy exceptions — typed error hierarchy for the Policy Engine.
"""

from __future__ import annotations


class PolicyError(Exception):
    """Base exception for all policy-related errors."""


class ValidationError(PolicyError):
    """Policy validation failure."""

    def __init__(self, message: str, policy_name: str = "") -> None:
        self.policy_name = policy_name
        super().__init__(f"{policy_name}: {message}" if policy_name else message)


class InheritanceError(PolicyError):
    """Circular or invalid policy inheritance."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class AssignmentError(PolicyError):
    """Machine policy assignment error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class OverrideError(PolicyError):
    """Machine policy override error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class PolicyNotFoundError(PolicyError):
    """Requested policy does not exist."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Policy not found: {name}")


class PolicyLoadError(PolicyError):
    """Policy YAML loading failure."""

    def __init__(self, name: str, detail: str = "") -> None:
        super().__init__(f"Failed to load policy '{name}': {detail}")


class PolicyRepositoryError(PolicyError):
    """Database error during policy operations."""
