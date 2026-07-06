"""
Fake Discord Adapter — simulates Discord notification delivery for testing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from integration_harness.time_controller import TimeController


class FakeDiscordAdapter:
    """Simulates the Discord Adapter for integration testing.

    Tracks rendered notifications and health state without connecting
    to the Discord API.
    """

    def __init__(self, time_controller: TimeController | None = None) -> None:
        self._time = time_controller or TimeController()
        self.notifications_rendered: list[dict[str, Any]] = []
        self.healthy: bool = True
        self.guilds_connected: int = 1

    async def render_notification(self, notification: dict[str, Any]) -> dict[str, Any]:
        """Simulate rendering and sending a notification to Discord."""
        result = {
            "notification_id": notification.get("notification_id", "unknown"),
            "event_type": notification.get("event_type", "unknown"),
            "severity": notification.get("severity", "info"),
            "rendered_at": datetime.fromtimestamp(self._time.now(), tz=UTC).isoformat(),
            "channel": self._get_channel(notification.get("severity", "info")),
            "sent": self.healthy,
        }
        self.notifications_rendered.append(result)
        return result

    def _get_channel(self, severity: str) -> str:
        if severity == "critical":
            return "critical-alerts"
        return "system-events"

    def set_unhealthy(self) -> None:
        """Simulate Discord adapter failure."""
        self.healthy = False

    def set_healthy(self) -> None:
        """Restore Discord adapter health."""
        self.healthy = True

    @property
    def notification_count(self) -> int:
        return len(self.notifications_rendered)
