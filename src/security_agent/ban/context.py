"""BanContext — immutable context for ban decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BanContext:
    """Immutable context for ban decisions."""

    settings: dict[str, Any] = field(default_factory=dict)
    logger: Any = None
