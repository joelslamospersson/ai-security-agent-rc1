"""
Notification exceptions — typed error hierarchy.
"""

from __future__ import annotations


class NotificationError(Exception):
    """Base exception for all notification-related errors."""


class NotificationValidationError(NotificationError):
    """Notification validation failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class FormatterError(NotificationError):
    """Notification formatting failure."""

    def __init__(self, template: str, detail: str = "") -> None:
        super().__init__(f"Formatter '{template}' error: {detail}")


class AdapterError(NotificationError):
    """Delivery adapter error."""

    def __init__(self, adapter: str, detail: str = "") -> None:
        super().__init__(f"Adapter '{adapter}' error: {detail}")


class QueueError(NotificationError):
    """Notification queue error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class DispatchError(NotificationError):
    """Notification dispatch error."""

    def __init__(self, notification_id: str, detail: str = "") -> None:
        super().__init__(f"Dispatch failed for {notification_id}: {detail}")


class NotificationRepositoryError(NotificationError):
    """Database error during notification operations."""


class UnknownDestinationError(NotificationError):
    """Unknown notification destination."""

    def __init__(self, destination: str) -> None:
        super().__init__(f"Unknown destination: {destination}")
