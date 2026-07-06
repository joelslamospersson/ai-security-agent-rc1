"""CorrelationContext — immutable context for correlation evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CorrelationContext:
    """Immutable context for correlation evaluation."""

    settings: dict[str, Any] = field(default_factory=dict)
    logger: Any = None
