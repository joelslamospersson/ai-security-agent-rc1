"""
Audit exceptions — typed error hierarchy.
"""

from __future__ import annotations


class AuditError(Exception):
    """Base exception for all audit-related errors."""


class AuditValidationError(AuditError):
    """Audit event validation failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class HashChainError(AuditError):
    """Hash chain integrity violation."""

    def __init__(self, audit_id: str, detail: str = "") -> None:
        super().__init__(f"Hash chain integrity error for {audit_id}: {detail}")


class ExportError(AuditError):
    """Audit export failure."""

    def __init__(self, format_name: str, detail: str = "") -> None:
        super().__init__(f"Export '{format_name}' failed: {detail}")


class RetentionError(AuditError):
    """Retention policy error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class AuditRepositoryError(AuditError):
    """Database error during audit operations."""
