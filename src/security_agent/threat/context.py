"""ThreatContext — immutable context for threat assessment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ThreatContext:
    """Immutable context for threat assessment."""

    settings: dict[str, Any] = field(default_factory=dict)
    logger: Any = None
