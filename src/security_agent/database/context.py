"""DatabaseContext — immutable context for database operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DatabaseContext:
    """Immutable context for database operations."""

    settings: dict[str, Any] = field(default_factory=dict)
    logger: Any = None
