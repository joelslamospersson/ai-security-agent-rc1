"""FirewallContext — immutable context for firewall operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FirewallContext:
    """Immutable context for firewall operations."""

    settings: dict[str, Any] = field(default_factory=dict)
    logger: Any = None
