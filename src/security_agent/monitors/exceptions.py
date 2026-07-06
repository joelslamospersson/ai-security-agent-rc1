"""
Monitor-specific exceptions.

All exceptions inherit from MonitorError base class.
"""

from __future__ import annotations


class MonitorError(Exception):
    """Base exception for all Monitor Framework errors."""


class MonitorNotFoundError(MonitorError):
    """Raised when a monitor name is not found in the registry."""


class MonitorRegistrationError(MonitorError):
    """Raised when a monitor cannot be registered (duplicate, invalid name)."""


class MonitorStartupError(MonitorError):
    """Raised when a monitor fails to start."""


class MonitorShutdownError(MonitorError):
    """Raised when a monitor fails to shut down."""


class MonitorNotRunningError(MonitorError):
    """Raised when a health check is attempted on a non-running monitor."""


class MonitorTimeoutError(MonitorError):
    """Raised when a monitor operation times out."""
