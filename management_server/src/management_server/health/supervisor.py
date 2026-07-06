"""
Health Supervisor — monitors all subsystems and generates health reports.

Every subsystem must expose: initialized, healthy, degraded, failed, shutdown.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from management_server.health.models import (
    HealthReport,
    HealthState,
    SubsystemHealth,
)

logger = structlog.get_logger("health.supervisor")

SUBSYSTEMS = [
    "certificates",
    "machines",
    "pairing",
    "heartbeat",
    "policies",
    "routing",
    "notifications",
    "audit",
    "commands",
    "configsync",
    "logging",
    "discord_bot",
    "database",
]


class HealthSupervisor:
    """Monitors health of all subsystems continuously."""

    def __init__(self) -> None:
        self._subsystems: dict[str, SubsystemHealth] = {}
        self._emergency_mode = False

    def register(
        self, name: str, state: HealthState = HealthState.UNINITIALIZED, message: str = ""
    ) -> None:
        """Register a subsystem for health monitoring."""
        self._subsystems[name] = SubsystemHealth(
            name=name,
            state=state,
            message=message,
        )

    def update(
        self,
        name: str,
        state: HealthState,
        message: str = "",
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """Update the health state of a subsystem."""
        if name not in self._subsystems:
            self.register(name, state, message)
        health = self._subsystems[name]
        old_state = health.state
        health.state = state
        health.last_check = datetime.now(tz=UTC)
        health.message = message
        if metrics:
            health.metrics.update(metrics)

        if old_state != state:
            logger.info(
                "Subsystem health changed",
                subsystem=name,
                from_state=old_state.value,
                to_state=state.value,
                message=message,
            )

    def get_health(self, name: str) -> SubsystemHealth | None:
        """Get health of a specific subsystem."""
        return self._subsystems.get(name)

    def get_report(self) -> HealthReport:
        """Generate a complete health report."""
        report = HealthReport(emergency_mode=self._emergency_mode)
        report.subsystems = dict(self._subsystems)

        healthy = 0
        degraded = 0
        failed = 0

        for health in self._subsystems.values():
            if health.state == HealthState.HEALTHY:
                healthy += 1
            elif health.state in (HealthState.DEGRADED,):
                degraded += 1
            elif health.state in (HealthState.FAILED, HealthState.UNINITIALIZED):
                failed += 1

        report.healthy_count = healthy
        report.degraded_count = degraded
        report.failed_count = failed

        if failed > 0:
            report.overall = HealthState.FAILED
        elif degraded > 0:
            report.overall = HealthState.DEGRADED
        elif healthy > 0:
            report.overall = HealthState.HEALTHY
        else:
            report.overall = HealthState.UNINITIALIZED

        return report

    async def check_all(self, managers: dict[str, Any]) -> HealthReport:
        """Check health of all managers."""
        for name, manager in managers.items():
            try:
                if hasattr(manager, "is_initialized") and manager.is_initialized:
                    self.update(name, HealthState.HEALTHY)
                elif hasattr(manager, "is_initialized"):
                    self.update(name, HealthState.UNINITIALIZED)
                else:
                    self.update(name, HealthState.HEALTHY)
            except Exception as e:
                self.update(name, HealthState.FAILED, str(e))

        return self.get_report()

    @property
    def emergency_mode(self) -> bool:
        return self._emergency_mode

    def set_emergency_mode(self, enabled: bool) -> None:
        self._emergency_mode = enabled
        logger.warning("Emergency mode", enabled=enabled)
