"""
Notification Manager — high-level facade for the Notification Engine.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.notifications.formatter import FormatterRegistry
from management_server.notifications.metrics import NotificationMetricsCollector
from management_server.notifications.queue import NotificationQueue
from management_server.notifications.repository import NotificationRepository
from management_server.notifications.schemas import (
    NotificationPreviewResponse,
    NotificationSchema,
)
from management_server.notifications.service import NotificationService

logger = structlog.get_logger("notifications.manager")


class NotificationManager:
    """High-level facade for the Notification Engine."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = NotificationRepository(session)
        self._queue = NotificationQueue()
        self._formatter_registry = FormatterRegistry()
        self._metrics = NotificationMetricsCollector()
        self._service = NotificationService(
            repository=self._repository,
            queue=self._queue,
            formatter_registry=self._formatter_registry,
            metrics=self._metrics,
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the notification manager."""
        self._initialized = True
        logger.info("Notification manager initialized")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def service(self) -> NotificationService:
        return self._service

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
        return await self._service.create_notification(
            routing_decision_id,
            machine_id,
            event_type,
            destination,
            priority,
            template,
            metadata,
        )

    async def get_notification(self, notification_id: str) -> NotificationSchema | None:
        return await self._service.get_notification(notification_id)

    async def list_notifications(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        result: dict[str, Any] = await self._service.list_notifications(limit, offset)
        return result

    async def preview(
        self,
        event_type: str,
        destination: str = "console",
        template: str = "detailed",
        metadata: dict[str, Any] | None = None,
    ) -> NotificationPreviewResponse:
        return await self._service.preview(event_type, destination, template, metadata)

    async def replay(
        self, routing_decision_id: str, destinations: list[str] | None = None
    ) -> list[NotificationSchema]:
        result: list[NotificationSchema] = await self._service.replay(
            routing_decision_id, destinations
        )
        return result

    async def get_queue_depth(self) -> dict[str, int]:
        result: dict[str, int] = await self._service.get_queue_depth()
        return result

    async def get_metrics(self) -> dict[str, int | float]:
        result: dict[str, int | float] = await self._service.get_metrics()
        return result
