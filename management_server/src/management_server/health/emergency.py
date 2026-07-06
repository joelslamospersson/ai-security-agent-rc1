"""
Emergency mode — read-only mode for disaster recovery.

Disables: remote commands, configuration publishing.
Continues: heartbeat, logging, audit, notifications.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger("health.emergency")


class EmergencyMode:
    """Read-only emergency mode for disaster recovery."""

    def __init__(self) -> None:
        self._active = False
        self._reason = ""
        self._disabled_subsystems: list[str] = []

    def activate(self, reason: str = "") -> None:
        """Activate emergency mode."""
        self._active = True
        self._reason = reason or "Emergency mode activated"
        self._disabled_subsystems = ["commands", "configsync"]
        logger.warning("Emergency mode activated", reason=reason)

    def deactivate(self) -> None:
        """Deactivate emergency mode."""
        self._active = False
        self._reason = ""
        self._disabled_subsystems = []
        logger.info("Emergency mode deactivated")

    def is_allowed(self, operation: str) -> bool:
        """Check if an operation is allowed in current mode."""
        if not self._active:
            return True
        return operation not in self._disabled_subsystems

    @property
    def active(self) -> bool:
        return self._active

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def disabled_subsystems(self) -> list[str]:
        return list(self._disabled_subsystems)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self._active,
            "reason": self._reason,
            "disabled_subsystems": list(self._disabled_subsystems),
        }
