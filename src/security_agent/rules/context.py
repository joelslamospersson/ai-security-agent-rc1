"""RuleContext — immutable context for rule evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import Logger
from typing import Any


@dataclass(frozen=True)
class RuleContext:
    """Immutable context passed to the Rule Engine during evaluation."""

    settings: dict[str, Any] = field(default_factory=dict)
    logger: Logger | None = None
    event_metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
