"""Correlation Engine exceptions."""

from __future__ import annotations


class CorrelationError(Exception):
    """Base exception for Correlation Engine errors."""


class ChainLoadError(CorrelationError):
    """Raised when an attack chain file cannot be loaded."""


class ChainValidationError(CorrelationError):
    """Raised when an attack chain fails validation."""


class ChainNotFoundError(CorrelationError):
    """Raised when an attack chain ID is not found."""


class IncidentError(CorrelationError):
    """Raised on invalid incident operations."""


class CorrelationKeyError(CorrelationError):
    """Raised when a correlation key is invalid."""
