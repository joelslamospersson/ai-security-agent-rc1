"""
Database dialect detection — identifies the active database backend.
"""

from __future__ import annotations

from enum import StrEnum, auto


class DatabaseDialect(StrEnum):
    """Supported database dialects."""

    POSTGRESQL = auto()
    SQLITE = auto()
    UNKNOWN = auto()


def detect_dialect(database_url: str) -> DatabaseDialect:
    """Detect the database dialect from the connection URL."""
    url_lower = database_url.lower()
    if "postgresql" in url_lower or "postgres" in url_lower:
        return DatabaseDialect.POSTGRESQL
    if "sqlite" in url_lower:
        return DatabaseDialect.SQLITE
    return DatabaseDialect.UNKNOWN


def dialect_to_migration_dir(dialect: DatabaseDialect) -> str:
    """Return the migration directory name for a dialect."""
    if dialect == DatabaseDialect.POSTGRESQL:
        return "postgres"
    if dialect == DatabaseDialect.SQLITE:
        return "sqlite"
    raise ValueError(f"No migration directory for dialect: {dialect}")


def is_sqlite(url: str) -> bool:
    return "sqlite" in url.lower()


def is_postgres(url: str) -> bool:
    return "postgresql" in url.lower() or "postgres" in url.lower()
