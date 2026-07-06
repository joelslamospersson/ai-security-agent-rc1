"""
SQLite backend — production-optimized SQLite with WAL mode.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from security_agent.database.backend import DatabaseBackend
from security_agent.database.exceptions import (
    ConnectionError,
    QueryError,
    TransactionError,
)

logger = logging.getLogger("database.sqlite")

SQLITE_PRAGMAS = [
    "PRAGMA journal_mode = WAL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA busy_timeout = 5000",
    "PRAGMA cache_size = -64000",
    "PRAGMA temp_store = MEMORY",
]


class SQLiteBackend(DatabaseBackend):  # type: ignore[misc]
    """Production-optimized SQLite with WAL mode."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        path = Path(self._db_path)
        if self._db_path != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                isolation_level=None,
            )
            self._conn.row_factory = sqlite3.Row
            for stmt in SQLITE_PRAGMAS:
                self._conn.execute(stmt)
            self._initialized = True
            logger.info("SQLite connected: %s", self._db_path)
        except sqlite3.Error as e:
            raise ConnectionError(f"Failed to connect: {e}") from e

    async def shutdown(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
            self._initialized = False

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        c = self._conn
        if c is None:
            raise QueryError("Not connected")
        try:
            cur = c.execute(sql, params)
            c.commit()
            return cur
        except sqlite3.Error as e:
            raise QueryError(f"Execute failed: {e}") from e

    async def execute_many(self, sql: str, params_list: list[tuple[Any, ...]]) -> Any:
        c = self._conn
        if c is None:
            raise QueryError("Not connected")
        try:
            c.executemany(sql, params_list)
            c.commit()
        except sqlite3.Error as e:
            raise QueryError(f"Batch execute failed: {e}") from e

    async def fetch_one(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> dict[str, Any] | None:
        c = self._conn
        if c is None:
            raise QueryError("Not connected")
        try:
            cur = c.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            raise QueryError(f"Fetch failed: {e}") from e

    async def fetch_all(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        c = self._conn
        if c is None:
            raise QueryError("Not connected")
        try:
            cur = c.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
        except sqlite3.Error as e:
            raise QueryError(f"Fetch all failed: {e}") from e

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[SQLiteBackend]:
        c = self._conn
        if c is None:
            raise TransactionError("Not connected")
        async with self._lock:
            try:
                c.execute("BEGIN")
                yield self
                c.commit()
            except sqlite3.Error as e:
                c.rollback()
                raise TransactionError(f"Transaction failed: {e}") from e

    async def health_check(self) -> bool:
        try:
            result = await self.fetch_one("SELECT 1 AS ok")
            return bool(result is not None and result.get("ok") == 1)
        except Exception:
            return False

    async def vacuum(self) -> None:
        await self.execute("VACUUM")

    @property
    def is_initialized(self) -> bool:
        return bool(self._initialized)
