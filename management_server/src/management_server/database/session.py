"""
Async SQLAlchemy session management.

Provides session factory, session context manager, and dependency injection.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from management_server.config.settings import Settings


def create_engine(settings: Settings) -> Any:
    """Create an async SQLAlchemy engine with connection pooling."""
    is_sqlite = "sqlite" in settings.database_url
    pool_args: dict[str, Any] = {}

    if not is_sqlite:
        pool_args.update(
            {
                "pool_size": 1 if settings.debug else settings.db_pool_size,
                "max_overflow": 0 if settings.debug else settings.db_max_overflow,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            }
        )

    poolclass = NullPool if (settings.debug or is_sqlite) else AsyncAdaptedQueuePool

    return create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        poolclass=poolclass,
        **pool_args,
    )


def create_session_factory(engine: Any) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory from an engine."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session for dependency injection."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
