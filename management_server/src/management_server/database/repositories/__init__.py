"""
Repository interfaces for the Management Server.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class Repository:
    """Base repository. All repositories inherit from this."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session


class MigrationRepository(Repository):
    """Repository for migration tracking."""

    async def get_current_version(self) -> int | None:
        """Return the current schema version."""
        from sqlalchemy import text

        result = await self._session.execute(
            text("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        )
        return result.scalar()

    async def get_migration_count(self) -> int:
        """Return the number of applied migrations."""
        from sqlalchemy import text

        result = await self._session.execute(text("SELECT COUNT(*) FROM migration_history"))
        return result.scalar() or 0
