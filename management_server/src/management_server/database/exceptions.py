"""Typed database exceptions for the Management Server."""

from __future__ import annotations


class DatabaseError(Exception):
    """Base exception for database errors."""


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""


class MigrationError(DatabaseError):
    """Raised when database migration fails."""


class TransactionError(DatabaseError):
    """Raised when a database transaction fails."""


class PoolError(DatabaseError):
    """Raised when connection pool acquisition fails."""


class HealthCheckError(DatabaseError):
    """Raised when database health check fails."""
