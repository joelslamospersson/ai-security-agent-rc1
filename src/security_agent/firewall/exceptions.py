"""Firewall abstraction exceptions."""

from __future__ import annotations


class FirewallError(Exception):
    """Base exception for Firewall abstraction errors."""


class UnsupportedBackendError(FirewallError):
    """Raised when a backend is not supported."""


class UnsupportedOperationError(FirewallError):
    """Raised when an operation is not supported by the backend."""


class BackendUnavailableError(FirewallError):
    """Raised when a backend is not available."""


class BackendRegistrationError(FirewallError):
    """Raised when backend registration fails."""


class SynchronizationError(FirewallError):
    """Raised when synchronization fails."""


class OperationValidationError(FirewallError):
    """Raised when an operation fails validation."""
