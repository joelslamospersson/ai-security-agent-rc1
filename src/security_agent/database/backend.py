"""Abstract DatabaseBackend interface for swappable database implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DatabaseBackend(ABC):
    """Abstract interface for database backends.

    Implementations:
        - sqlite.py
        - postgres.py (future)
        - mysql.py (future)
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Open connection, run migrations."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Close connection, release resources."""

    @abstractmethod
    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        """Execute a single statement."""

    @abstractmethod
    async def execute_many(self, sql: str, params_list: list[tuple[Any, ...]]) -> Any:
        """Execute a statement with many parameter sets."""

    @abstractmethod
    async def fetch_one(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> dict[str, Any] | None:
        """Fetch a single row as dict."""

    @abstractmethod
    async def fetch_all(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        """Fetch all rows as list of dicts."""

    @abstractmethod
    async def transaction(self) -> Any:
        """Return a context manager for transactions."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the database is operational."""

    @abstractmethod
    async def vacuum(self) -> None:
        """Reclaim storage space."""
