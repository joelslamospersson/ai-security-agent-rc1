"""
Dialect-aware migration manager.

Loads SQL migration files from:
    migrations/postgres/  (for PostgreSQL)
    migrations/sqlite/    (for SQLite)

No runtime SQL rewriting. No compromises to PostgreSQL schema.
"""

from __future__ import annotations

from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from management_server.database.dialect import DatabaseDialect, dialect_to_migration_dir

logger = structlog.get_logger("database.migrations")

MIGRATIONS_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "migrations"


def _discover_migration_files(dialect: DatabaseDialect) -> list[Path]:
    """Discover SQL migration files for the given dialect, sorted by name."""
    subdir = dialect_to_migration_dir(dialect)
    dir_path = MIGRATIONS_ROOT / subdir
    if not dir_path.exists():
        logger.warning("Migration directory not found", path=str(dir_path))
        return []
    files = sorted(dir_path.glob("*.sql"))
    logger.info(
        "Discovered migration files",
        dialect=dialect.value,
        count=len(files),
        directory=str(dir_path),
    )
    return files


async def run_migrations(conn: AsyncConnection, dialect: DatabaseDialect) -> None:
    """Run all migration files for the given dialect in order."""
    files = _discover_migration_files(dialect)
    for path in files:
        logger.info("Running migration", file=path.name)
        sql = path.read_text()
        # Split by semicolons to execute individual statements
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            await conn.execute(text(stmt))
        logger.info("Migration complete", file=path.name)


async def run_migrations_for_url(database_url: str, conn: AsyncConnection) -> None:
    """Auto-detect dialect and run appropriate migrations."""
    from management_server.database.dialect import detect_dialect

    dialect = detect_dialect(database_url)
    await run_migrations(conn, dialect)
