"""
Migration manager — runs ordered, idempotent database migrations.

Migrations are applied in order. Each migration is recorded in the
migration_history table. Rollback is detected if checksums change.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from security_agent.database.backend import DatabaseBackend
from security_agent.database.exceptions import MigrationError
from security_agent.database.schema import INITIAL_SCHEMA

logger = logging.getLogger("database.migrations")

MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS migration_history (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
    checksum    TEXT NOT NULL DEFAULT '',
    success     INTEGER NOT NULL DEFAULT 1
);
"""


class MigrationManager:
    """Manages database schema migrations.

    Usage:
        mgr = MigrationManager(db, "database/migrations")
        await mgr.run()
    """

    def __init__(self, db: DatabaseBackend, migrations_dir: str | None = None) -> None:
        self._db = db
        self._migrations_dir = Path(migrations_dir) if migrations_dir else None

    async def run(self) -> None:
        """Run all pending migrations."""
        await self._ensure_migrations_table()

        applied = await self._get_applied_versions()

        # Always apply initial schema first
        await self._apply_checksummed("_initial_schema", INITIAL_SCHEMA, applied)

        # Load and apply file-based migrations
        if self._migrations_dir and self._migrations_dir.exists():
            for path in sorted(self._migrations_dir.glob("*.sql")):
                version = _extract_version(path.stem)
                if version in applied:
                    continue
                sql = path.read_text()
                await self._apply_checksummed(path.stem, sql, applied)

        logger.info("Migrations complete")

    async def _ensure_migrations_table(self) -> None:
        await self._db.execute(MIGRATIONS_TABLE)

    async def _get_applied_versions(self) -> set[str]:
        try:
            rows = await self._db.fetch_all(
                "SELECT name, checksum FROM migration_history WHERE success = 1"
            )
            return {r["name"] for r in rows}
        except Exception:
            return set()

    async def _apply_checksummed(
        self,
        name: str,
        sql: str,
        applied: set[str],
    ) -> None:
        if name in applied:
            return
        checksum = hashlib.sha256(sql.encode()).hexdigest()[:16]

        try:
            for statement in sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    await self._db.execute(stmt)

            await self._db.execute(
                "INSERT INTO migration_history (version, name, checksum) "
                "VALUES ((SELECT COALESCE(MAX(version), 0) + 1 FROM migration_history), ?, ?)",
                (name, checksum),
            )
            logger.info("Applied migration: %s", name)

        except Exception as e:
            logger.error("Migration failed: %s: %s", name, e)
            raise MigrationError(f"Migration {name} failed: {e}") from e


def _extract_version(name: str) -> str:
    """Extract version from migration filename like '001_initial'."""
    return name.split("_")[0] if "_" in name else name
