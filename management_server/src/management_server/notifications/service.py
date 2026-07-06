"""
Notification service — orchestrates notification creation, formatting, queueing, and dispatch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from management_server.notifications.adapters import AdapterRegistry
from management_server.notifications.dispatcher import NotificationDispatcher
from management_server.notifications.exceptions import (
    NotificationError,
    NotificationValidationError,
)
from management_server.notifications.formatter import FormatterRegistry
from management_server.notifications.metrics import NotificationMetricsCollector
from management_server.notifications.models import (
    DeliveryResult,
    Notification,
    NotificationStatus,
)
from management_server.notifications.queue import NotificationQueue
from management_server.notifications.repository import NotificationRepository
from management_server.notifications.schemas import (
    NotificationPreviewResponse,
    NotificationSchema,
)
from management_server.notifications.validator import NotificationValidator

logger = structlog.get_logger("notifications.service")


class NotificationService:
    """Notification Engine service.

    Pipeline:
        RoutingDecision → Validate → Format → Create Notification
        → Queue → Dispatch → DeliveryResult
    """

    def __init__(
        self,
        repository: NotificationRepository,
        queue: NotificationQueue | None = None,
        formatter_registry: FormatterRegistry | None = None,
        adapter_registry: AdapterRegistry | None = None,
        metrics: NotificationMetricsCollector | None = None,
    ) -> None:
        self._repository = repository
        self._queue = queue or NotificationQueue()
        self._formatter_registry = formatter_registry or FormatterRegistry()
        self._adapter_registry = adapter_registry or AdapterRegistry()
        self._dispatcher = NotificationDispatcher(self._queue, self._adapter_registry)
        self._validator = NotificationValidator()
        self._metrics = metrics or NotificationMetricsCollector()

    async def create_notification(
        self,
        routing_decision_id: str,
        machine_id: str,
        event_type: str,
        destination: str,
        priority: str = "normal",
        template: str = "detailed",
        metadata: dict[str, Any] | None = None,
    ) -> NotificationSchema:
        """Create a notification from a routing decision."""
        # Format payload
        fmt_start = datetime.now(tz=UTC)
        try:
            formatter = self._formatter_registry.get_or_default(template)
            payload = formatter.format(
                event_type=event_type,
                machine_id=machine_id,
                destination=destination,
                priority=priority,
                metadata=metadata,
            )
        except Exception as e:
            raise NotificationError(f"Formatting failed: {e}") from e

        fmt_latency = (datetime.now(tz=UTC) - fmt_start).total_seconds() * 1000
        self._metrics.formatter_latency(fmt_latency)

        # Create notification
        notification = Notification.create(
            routing_decision_id=routing_decision_id,
            machine_id=machine_id,
            event_type=event_type,
            destination=destination,
            priority=priority,
            template=formatter.name,
            payload=payload,
            metadata=metadata,
        )

        # Validate
        errors = self._validator.validate_notification(notification)
        if errors:
            raise NotificationValidationError(errors[0])

        # Persist
        await self._repository.save_notification(notification)
        self._metrics.notification_created()

        logger.info(
            "Notification created",
            notification_id=notification.notification_id,
            event_type=event_type,
            destination=destination,
        )

        return self._to_schema(notification)

    async def queue_notification(self, notification_id: str, priority: str = "normal") -> None:
        """Queue an existing notification for dispatch."""
        record = await self._repository.get_notification(notification_id)
        if record is None:
            raise NotificationError(f"Notification not found: {notification_id}")

        notification = Notification(
            notification_id=record.get("notification_id", ""),
            routing_decision_id=record.get("routing_decision_id", ""),
            machine_id=record.get("machine_id", ""),
            event_type=record.get("event_type", ""),
            destination=record.get("destination", ""),
            priority=record.get("priority", "normal"),
            template=record.get("template", "detailed"),
            payload=record.get("payload", ""),
            status=NotificationStatus.QUEUED,
        )

        await self._queue.enqueue(notification, priority)
        await self._repository.update_status(notification_id, NotificationStatus.QUEUED.value)
        self._metrics.notification_queued()

        logger.info(
            "Notification queued",
            notification_id=notification_id,
            queue=priority,
        )

    async def dispatch(self, notification_id: str) -> DeliveryResult:
        """Dispatch a single notification."""
        record = await self._repository.get_notification(notification_id)
        if record is None:
            raise NotificationError(f"Notification not found: {notification_id}")

        notification = Notification(
            notification_id=record.get("notification_id", ""),
            routing_decision_id=record.get("routing_decision_id", ""),
            machine_id=record.get("machine_id", ""),
            event_type=record.get("event_type", ""),
            destination=record.get("destination", ""),
            priority=record.get("priority", "normal"),
            template=record.get("template", "detailed"),
            payload=record.get("payload", ""),
            status=NotificationStatus(record.get("status", "pending")),
        )

        result = await self._dispatcher.dispatch(notification)
        self._metrics.delivery_attempt()

        if result.status.value in ("failed", "retry", "skipped"):
            self._metrics.skipped()

        # Record delivery result
        await self._repository.save_delivery_result(
            notification_id=notification_id,
            status=result.status.value,
            adapter=result.adapter,
            latency_ms=result.latency_ms,
            error_code=result.error_code,
            error_message=result.error_message,
        )

        await self._repository.update_status(notification_id, NotificationStatus.DISPATCHED.value)

        self._metrics.notification_dispatched()

        return result

    async def preview(
        self,
        event_type: str,
        destination: str = "console",
        template: str = "detailed",
        metadata: dict[str, Any] | None = None,
    ) -> NotificationPreviewResponse:
        """Preview a notification without creating or persisting it."""
        formatter = self._formatter_registry.get_or_default(template)
        payload = formatter.format(
            event_type=event_type,
            machine_id="preview",
            destination=destination,
            priority="normal",
            metadata=metadata,
        )
        return NotificationPreviewResponse(
            template=formatter.name,
            payload=payload,
            estimated_size_bytes=len(payload.encode()),
        )

    async def replay(
        self,
        routing_decision_id: str,
        override_destinations: list[str] | None = None,
    ) -> list[NotificationSchema]:
        """Replay notifications from a routing decision (recreate, no delivery)."""
        destinations = override_destinations or ["console"]
        schemas: list[NotificationSchema] = []
        for dest in destinations:
            schema = await self.create_notification(
                routing_decision_id=routing_decision_id,
                machine_id="replay",
                event_type="replay",
                destination=dest,
            )
            schemas.append(schema)
        return schemas

    async def get_notification(self, notification_id: str) -> NotificationSchema | None:
        """Get a notification by ID."""
        record = await self._repository.get_notification(notification_id)
        if record is None:
            return None
        return NotificationSchema(
            notification_id=record.get("notification_id", ""),
            routing_decision_id=record.get("routing_decision_id", ""),
            machine_id=record.get("machine_id", ""),
            event_type=record.get("event_type", ""),
            destination=record.get("destination", ""),
            priority=record.get("priority", "normal"),
            template=record.get("template", "detailed"),
            payload=record.get("payload", ""),
            status=record.get("status", "pending"),
            created_at=record.get("created_at"),
        )

    async def list_notifications(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """List notifications."""
        records, total = await self._repository.list_notifications(limit, offset)
        notifications = []
        for r in records:
            notifications.append(
                NotificationSchema(
                    notification_id=r.get("notification_id", ""),
                    routing_decision_id=r.get("routing_decision_id", ""),
                    machine_id=r.get("machine_id", ""),
                    event_type=r.get("event_type", ""),
                    destination=r.get("destination", ""),
                    priority=r.get("priority", "normal"),
                    template=r.get("template", "detailed"),
                    payload=r.get("payload", ""),
                    status=r.get("status", "pending"),
                    created_at=r.get("created_at"),
                )
            )
        return {"notifications": notifications, "total": total}

    async def get_queue_depth(self) -> dict[str, int]:
        """Get queue depth for all priorities."""
        depth = self._queue.depth()
        if isinstance(depth, dict):
            return depth
        return {"total": depth}

    async def get_metrics(self) -> dict[str, int | float]:
        """Get notification metrics."""
        notif_count = await self._repository.get_notification_count()
        delivery_count = await self._repository.get_delivery_count()
        queue_depth = self._queue.total_pending
        snap = self._metrics.snapshot(queue_depth=queue_depth)
        return {
            "notifications_created": notif_count,
            "notifications_queued": snap.notifications_queued,
            "notifications_dispatched": snap.notifications_dispatched,
            "formatter_latency_ms": snap.formatter_latency_ms,
            "queue_depth": queue_depth,
            "delivery_attempts": delivery_count,
            "skipped_notifications": snap.skipped_notifications,
        }

    @staticmethod
    def _to_schema(notification: Notification) -> NotificationSchema:
        return NotificationSchema(
            notification_id=notification.notification_id,
            routing_decision_id=notification.routing_decision_id,
            machine_id=notification.machine_id,
            event_type=notification.event_type,
            destination=notification.destination,
            priority=notification.priority,
            template=notification.template,
            payload=notification.payload,
            status=notification.status.value,
            created_at=notification.created_at,
        )
