"""
Notification dispatcher — dispatches notifications to delivery adapters.

Simulates dispatching; no actual external delivery is performed.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from management_server.notifications.adapters import AdapterRegistry
from management_server.notifications.models import DeliveryResult, Notification
from management_server.notifications.queue import NotificationQueue

logger = structlog.get_logger("notifications.dispatcher")


class NotificationDispatcher:
    """Dispatches notifications from the queue to delivery adapters.

    For each notification:
        1. Look up adapter for destination
        2. Call deliver()
        3. Record DeliveryResult
        4. Update notification status
    """

    def __init__(
        self,
        queue: NotificationQueue,
        adapter_registry: AdapterRegistry | None = None,
    ) -> None:
        self._queue = queue
        self._adapter_registry = adapter_registry or AdapterRegistry()

    async def dispatch(self, notification: Notification) -> DeliveryResult:
        """Dispatch a single notification to its destination adapter."""
        adapter = self._adapter_registry.get(notification.destination)
        start = datetime.now(tz=UTC)

        logger.info(
            "Dispatching notification",
            notification_id=notification.notification_id,
            destination=notification.destination,
            adapter=adapter.name,
        )

        result = await adapter.deliver(notification)

        elapsed = (datetime.now(tz=UTC) - start).total_seconds() * 1000
        logger.info(
            "Dispatch result",
            notification_id=notification.notification_id,
            status=result.status.value,
            latency_ms=round(elapsed, 2),
        )

        return result

    async def dispatch_from_queue(self, priority: str = "normal") -> DeliveryResult | None:
        """Dequeue and dispatch a single notification from the given priority queue."""
        item = self._queue.dequeue_nowait(priority)
        if item is None:
            return None
        return await self.dispatch(item.notification)

    async def dispatch_all(self, priority: str | None = None) -> list[DeliveryResult]:
        """Dispatch all queued notifications, optionally for a specific priority."""
        results: list[DeliveryResult] = []
        priorities = [priority] if priority else ["immediate", "high", "normal", "low", "bulk"]

        for p in priorities:
            while True:
                result = await self.dispatch_from_queue(p)
                if result is None:
                    break
                results.append(result)

        return results
