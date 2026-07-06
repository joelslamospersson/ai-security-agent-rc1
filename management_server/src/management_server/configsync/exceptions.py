"""
Config sync exceptions — typed error hierarchy.
"""

from __future__ import annotations


class ConfigSyncError(Exception):
    """Base exception for all config sync errors."""


class PackageNotFoundError(ConfigSyncError):
    """Configuration package not found."""

    def __init__(self, package_id: str) -> None:
        super().__init__(f"Package not found: {package_id}")


class PackageValidationError(ConfigSyncError):
    """Package validation failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidTransitionError(ConfigSyncError):
    """Illegal package lifecycle transition."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Cannot transition from {current} to {target}")


class IntegrityError(ConfigSyncError):
    """Package integrity verification failure."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(f"Integrity check failed: {detail}")


class VersionMismatchError(ConfigSyncError):
    """Agent version incompatible with package."""

    def __init__(self, agent_version: str, minimum_required: str) -> None:
        super().__init__(f"Agent v{agent_version} below minimum v{minimum_required}")


class ConfigSyncRepositoryError(ConfigSyncError):
    """Database error during config sync operations."""
