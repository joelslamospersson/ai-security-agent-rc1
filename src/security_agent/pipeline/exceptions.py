"""
Pipeline-specific exceptions.

All exceptions inherit from PipelineError base class.
"""

from __future__ import annotations


class PipelineError(Exception):
    """Base exception for all Pipeline Engine errors."""


class StageNotFoundError(PipelineError):
    """Raised when a stage name is not found in the registry."""


class StageRegistrationError(PipelineError):
    """Raised when a stage cannot be registered (duplicate, cycle, etc.)."""


class PipelineCancelledError(PipelineError):
    """Raised when an operation is attempted on a cancelled pipeline."""


class PipelineShutdownError(PipelineError):
    """Raised when an operation is attempted during pipeline shutdown."""


class StageInitializationError(PipelineError):
    """Raised when a stage fails to initialize."""


class RetryExhaustedError(PipelineError):
    """Raised when a stage has exhausted its retry attempts."""
