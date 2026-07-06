"""ReputationContext — immutable context for reputation operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReputationContext:
    """Immutable context for reputation operations."""

    settings: dict[str, Any] = field(default_factory=dict)
    logger: Any = None
