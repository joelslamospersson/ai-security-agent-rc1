"""
Notification validator — validates notification data before creation.
"""

from __future__ import annotations

import structlog

from management_server.notifications.exceptions import NotificationValidationError
from management_server.notifications.formatter import FormatterRegistry
from management_server.notifications.models import Notification

logger = structlog.get_logger("notifications.validator")

KNOWN_PRIORITIES = {"immediate", "high", "normal", "low", "bulk"}

KNOWN_DESTINATIONS = {
    "discord",
    "email",
    "webhook",
    "syslog",
    "dashboard",
    "archive",
    "console",
    "none",
}

KNOWN_TEMPLATES = {"minimal", "detailed", "discord_embed", "markdown", "json", "plain_text"}


class NotificationValidator:
    """Validates notification data before queueing."""

    def __init__(self) -> None:
        self._formatter_registry = FormatterRegistry()

    def validate_notification(self, notification: Notification) -> list[str]:
        """Validate a notification. Returns list of error messages."""
        errors: list[str] = []

        if not notification.notification_id:
            errors.append("notification_id is required")
        if not notification.routing_decision_id:
            errors.append("routing_decision_id is required")
        if not notification.machine_id:
            errors.append("machine_id is required")
        if not notification.event_type:
            errors.append("event_type is required")

        if notification.destination not in KNOWN_DESTINATIONS:
            errors.append(f"Unknown destination: '{notification.destination}'")

        if notification.priority not in KNOWN_PRIORITIES:
            errors.append(f"Invalid priority: '{notification.priority}'")

        template = notification.template.lower()
        if template not in KNOWN_TEMPLATES:
            errors.append(f"Unknown template: '{template}'")

        return errors

    def validate_and_raise(self, notification: Notification) -> None:
        """Validate and raise on first error."""
        errors = self.validate_notification(notification)
        if errors:
            raise NotificationValidationError(errors[0])

    @staticmethod
    def validate_preview(
        event_type: str,
        destination: str,
        template: str,
    ) -> list[str]:
        """Validate preview request parameters."""
        errors: list[str] = []
        if not event_type:
            errors.append("event_type is required")
        if destination and destination not in KNOWN_DESTINATIONS:
            errors.append(f"Unknown destination: '{destination}'")
        if template and template.lower() not in KNOWN_TEMPLATES:
            errors.append(f"Unknown template: '{template}'")
        return errors
