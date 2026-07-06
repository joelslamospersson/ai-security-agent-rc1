"""
Database connection manager for the Management Server.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from management_server.config.settings import Settings
from management_server.database.exceptions import ConnectionError, MigrationError
from management_server.database.session import create_engine, create_session_factory

logger = structlog.get_logger("database.backend")


class DatabaseBackend:
    """Manages the database engine, session factory, and lifecycle."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine: Any = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Create engine, session factory, and run migrations."""
        try:
            self._engine = create_engine(self._settings)
            self._session_factory = create_session_factory(self._engine)

            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

            await self._run_migrations()
            self._initialized = True
            logger.info(
                "Database connected",
                host=self._settings.db_host,
                port=self._settings.db_port,
                database=self._settings.db_database,
                pool_size=self._settings.db_pool_size,
            )
        except Exception as e:
            raise ConnectionError(f"Failed to initialize database: {e}") from e

    async def shutdown(self) -> None:
        """Dispose the engine and release all connections."""
        if self._engine:
            await self._engine.dispose()
            self._initialized = False
            logger.info("Database disconnected")

    async def health_check(self) -> dict[str, object]:
        """Check database connectivity and return status."""
        result: dict[str, object] = {
            "connected": False,
            "migration_version": None,
            "pool_size": None,
        }
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            result["connected"] = True
            result["pool_size"] = self._settings.db_pool_size

            try:
                async with self.session_factory() as session:
                    from sqlalchemy import text as sa_text

                    row = await session.execute(
                        sa_text(
                            "SELECT version FROM migration_history ORDER BY version DESC LIMIT 1"
                        )
                    )
                    val = row.scalar()
                    result["migration_version"] = val
            except Exception:
                result["migration_version"] = None

        except Exception as e:
            result["error"] = str(e)
        return result

    async def _run_migrations(self) -> None:
        """Create infrastructure tables using dialect-aware migrations."""
        from management_server.database.dialect import detect_dialect
        from management_server.database.migrations import run_migrations

        try:
            async with self._engine.begin() as conn:
                dialect = detect_dialect(self._settings.database_url)
                await run_migrations(conn, dialect)
            logger.info("Database migrations complete", dialect=dialect.value)
        except Exception as e:
            raise MigrationError(f"Migration failed: {e}") from e

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise ConnectionError("Database not initialized")
        return self._session_factory

    @property
    def is_initialized(self) -> bool:
        return self._initialized
