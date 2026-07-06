"""Database layer exceptions."""

from __future__ import annotations


class DatabaseError(Exception):
    """Base exception for Database errors."""


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""


class MigrationError(DatabaseError):
    """Raised when migration fails."""


class QueryError(DatabaseError):
    """Raised when a query fails."""


class IntegrityError(DatabaseError):
    """Raised on constraint violations."""


class TransactionError(DatabaseError):
    """Raised when a transaction fails."""


class RepositoryError(DatabaseError):
    """Raised when a repository operation fails."""
