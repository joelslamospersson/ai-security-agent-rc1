"""
Logging exceptions — typed error hierarchy.
"""

from __future__ import annotations


class LoggingError(Exception):
    """Base exception for all logging framework errors."""


class LogWriteError(LoggingError):
    """Failed to write log entry."""

    def __init__(self, path: str, detail: str = "") -> None:
        super().__init__(f"Log write failed: {path}: {detail}")


class RotationError(LoggingError):
    """Log rotation failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class CompressionError(LoggingError):
    """Log compression failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class RetentionError(LoggingError):
    """Retention policy failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ReportError(LoggingError):
    """Report generation failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
