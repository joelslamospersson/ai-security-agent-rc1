"""Detector-specific exceptions."""

from __future__ import annotations


class DetectorError(Exception):
    """Base exception for all Detector Framework errors."""


class DetectorNotFoundError(DetectorError):
    """Raised when a detector name is not found."""


class DetectorRegistrationError(DetectorError):
    """Raised when a detector cannot be registered (duplicate, invalid)."""


class DetectorInitializationError(DetectorError):
    """Raised when a detector fails to initialize."""


class UnsupportedEventError(DetectorError):
    """Raised when a detector receives an unsupported event type."""


class InvalidDetectionResultError(DetectorError):
    """Raised when a detector returns an invalid detection result."""


class DetectorExecutionError(DetectorError):
    """Raised when a detector fails during analysis."""
