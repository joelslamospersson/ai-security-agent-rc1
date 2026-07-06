"""
Notification adapters — abstract interface for delivery adapters.

No adapters perform actual delivery. This module defines the interface
that future Discord, Email, Webhook, etc. adapters will implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import structlog

from management_server.notifications.models import (
    DeliveryResult,
    DeliveryResultStatus,
    Notification,
)

logger = structlog.get_logger("notifications.adapters")


class NotificationAdapter(ABC):
    """Abstract base class for all delivery adapters.

    Subclasses implement `deliver()` to send notifications to a specific
    destination (Discord, Email, Webhook, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique adapter name matching a destination type."""
        ...

    @abstractmethod
    async def deliver(self, notification: Notification) -> DeliveryResult:
        """Deliver a notification.

        Returns a DeliveryResult indicating success, failure, or retry.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the adapter is healthy and configured."""
        ...


class ConsoleAdapter(NotificationAdapter):
    """Console adapter — logs notifications to stdout for development."""

    name = "console"

    async def deliver(self, notification: Notification) -> DeliveryResult:
        logger.info(
            "Console delivery",
            notification_id=notification.notification_id,
            event_type=notification.event_type,
            destination=notification.destination,
            payload_size=len(notification.payload),
        )
        return DeliveryResult.success(
            notification_id=notification.notification_id,
            adapter=self.name,
            latency_ms=0.5,
        )

    async def health_check(self) -> bool:
        return True


class ArchiveAdapter(NotificationAdapter):
    """Archive adapter — stores notifications for later retrieval.

    Delivery is performed by the repository persistence; this adapter
    simply records that archival was requested.
    """

    name = "archive"

    async def deliver(self, notification: Notification) -> DeliveryResult:
        logger.info(
            "Archive delivery requested",
            notification_id=notification.notification_id,
        )
        return DeliveryResult.success(
            notification_id=notification.notification_id,
            adapter=self.name,
            latency_ms=0.3,
        )

    async def health_check(self) -> bool:
        return True


class NoopAdapter(NotificationAdapter):
    """No-op adapter for unknown/unsupported destinations.

    Returns SKIPPED to indicate no actual delivery was attempted.
    """

    name = "none"

    async def deliver(self, notification: Notification) -> DeliveryResult:
        logger.warning(
            "No adapter for notification",
            notification_id=notification.notification_id,
            destination=notification.destination,
        )
        return DeliveryResult(
            result_id="",
            notification_id=notification.notification_id,
            status=DeliveryResultStatus.SKIPPED,
            adapter=self.name,
        )

    async def health_check(self) -> bool:
        return False


class AdapterRegistry:
    """Registry of available delivery adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, NotificationAdapter] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for adapter in [ConsoleAdapter(), ArchiveAdapter(), NoopAdapter()]:
            self._adapters[adapter.name] = adapter

    def register(self, adapter: NotificationAdapter) -> None:
        """Register a custom adapter."""
        self._adapters[adapter.name] = adapter

    def get(self, destination: str) -> NotificationAdapter:
        """Get an adapter for a destination. Falls back to NoopAdapter."""
        adapter = self._adapters.get(destination)
        if adapter is None:
            logger.warning("No adapter registered for destination", destination=destination)
            return self._adapters.get("none", NoopAdapter())
        return adapter

    @property
    def available(self) -> list[str]:
        return list(self._adapters.keys())
