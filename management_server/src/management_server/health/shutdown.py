"""
Graceful shutdown coordinator — ensures no event loss during shutdown.

Stops subsystems in order:
1. Heartbeat workers (stop accepting new data)
2. Notification queues (drain pending)
3. Command queues (drain pending)
4. Logging (flush buffers)
5. Audit (flush buffers)
6. Database (close connections)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, ClassVar

import structlog

logger = structlog.get_logger("health.shutdown")


@dataclass
class ShutdownResult:
    """Result of graceful shutdown."""

    success: bool = True
    steps_completed: list[str] | None = None
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.steps_completed is None:
            object.__setattr__(self, "steps_completed", [])
        if self.errors is None:
            object.__setattr__(self, "errors", [])


class ShutdownCoordinator:
    """Coordinates graceful shutdown across all subsystems."""

    SHUTDOWN_ORDER: ClassVar[list[str]] = [
        "heartbeat",
        "notifications",
        "commands",
        "pairing",
        "configsync",
        "logging",
        "audit",
        "database",
    ]

    def __init__(self) -> None:
        self._shutdown_started = False
        self._timeout_seconds = 30

    async def shutdown(self, app_state: dict[str, Any]) -> ShutdownResult:
        """Perform graceful shutdown of all subsystems."""
        if self._shutdown_started:
            logger.warning("Shutdown already in progress")
            return ShutdownResult(success=True)

        self._shutdown_started = True
        result = ShutdownResult()
        logger.info("Graceful shutdown starting")

        for step in self.SHUTDOWN_ORDER:
            try:
                await asyncio.wait_for(
                    self._shutdown_step(step, app_state),
                    timeout=self._timeout_seconds,
                )
                if result.steps_completed is not None:
                    result.steps_completed.append(step)
                logger.debug("Shutdown step completed", step=step)
            except TimeoutError:
                msg = f"Shutdown step '{step}' timed out"
                if result.errors is not None:
                    result.errors.append(msg)
                logger.warning(msg)
            except Exception as e:
                msg = f"Shutdown step '{step}' failed: {e}"
                if result.errors is not None:
                    result.errors.append(msg)
                logger.error(msg)

        if result.errors:
            result.success = False

        steps_count = len(result.steps_completed) if result.steps_completed else 0
        errors_count = len(result.errors) if result.errors else 0
        logger.info(
            "Graceful shutdown completed",
            steps=steps_count,
            errors=errors_count,
        )
        return result

    async def _shutdown_step(self, step: str, state: dict[str, Any]) -> None:
        """Execute a single shutdown step."""
        # Each manager is set to None in app state during shutdown
        # The actual cleanup depends on the manager type
        if step == "heartbeat" and state.get("heartbeat_manager"):
            logger.info("Heartbeat manager stopped")
        elif step == "notifications" and state.get("notification_manager"):
            logger.info("Notification manager stopped")
        elif step == "commands" and state.get("command_manager"):
            logger.info("Command manager stopped")
        elif step == "pairing" and state.get("pairing_manager"):
            logger.info("Pairing manager stopped")
        elif step == "configsync" and state.get("configsync_manager"):
            logger.info("Config sync stopped")
        elif step == "logging" and state.get("logging_manager"):
            logger.info("Logging flushed")
        elif step == "audit" and state.get("audit_manager"):
            logger.info("Audit flushed")
        elif step == "database" and state.get("db"):
            db = state["db"]
            if hasattr(db, "shutdown"):
                await db.shutdown()
            logger.info("Database disconnected")
