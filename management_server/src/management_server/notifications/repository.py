"""
Notification repository — database CRUD for notifications and delivery results.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.notifications.models import Notification

logger = structlog.get_logger("notifications.repository")


class NotificationRepository:
    """Persists notifications and delivery results."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_notification(self, notification: Notification) -> dict[str, Any]:
        """Persist a notification."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                INSERT INTO notifications (id, notification_id, routing_decision_id,
                    machine_id, event_type, destination, priority, template,
                    payload, metadata_json, status, created_at)
                VALUES (:id, :nid, :rdid, :mid, :et, :dest, :pri, :tmpl,
                    :payload, :meta, :status, :now)
            """),
            {
                "id": str(uuid.uuid4()),
                "nid": notification.notification_id,
                "rdid": notification.routing_decision_id,
                "mid": notification.machine_id,
                "et": notification.event_type,
                "dest": notification.destination,
                "pri": notification.priority,
                "tmpl": notification.template,
                "payload": notification.payload,
                "meta": json.dumps(notification.metadata),
                "status": notification.status.value,
                "now": now,
            },
        )
        await self._session.commit()
        return {"notification_id": notification.notification_id}

    async def get_notification(self, notification_id: str) -> dict[str, Any] | None:
        """Get a notification by ID."""
        result = await self._session.execute(
            text("SELECT * FROM notifications WHERE notification_id = :nid"),
            {"nid": notification_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def list_notifications(
        self, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """List notifications with pagination."""
        count = await self._session.execute(text("SELECT COUNT(*) FROM notifications"))
        total = count.scalar() or 0

        result = await self._session.execute(
            text("""
                SELECT * FROM notifications
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset},
        )
        rows = [dict(r._mapping) for r in result.fetchall()]
        return rows, total

    async def update_status(self, notification_id: str, status: str) -> None:
        """Update notification status."""
        await self._session.execute(
            text("""
                UPDATE notifications
                SET status = :status, updated_at = :now
                WHERE notification_id = :nid
            """),
            {"nid": notification_id, "status": status, "now": datetime.now(tz=UTC)},
        )
        await self._session.commit()

    async def save_delivery_result(
        self,
        notification_id: str,
        status: str,
        adapter: str,
        latency_ms: float = 0.0,
        error_code: str = "",
        error_message: str = "",
    ) -> None:
        """Persist a delivery result (append-only)."""
        await self._session.execute(
            text("""
                INSERT INTO delivery_results (id, notification_id, status,
                    adapter, latency_ms, error_code, error_message, created_at)
                VALUES (:id, :nid, :status, :adapter, :lat, :ec, :em, :now)
            """),
            {
                "id": str(uuid.uuid4()),
                "nid": notification_id,
                "status": status,
                "adapter": adapter,
                "lat": latency_ms,
                "ec": error_code,
                "em": error_message,
                "now": datetime.now(tz=UTC),
            },
        )
        await self._session.commit()

    async def get_delivery_results(self, notification_id: str) -> list[dict[str, Any]]:
        """Get all delivery results for a notification (append-only history)."""
        result = await self._session.execute(
            text("""
                SELECT * FROM delivery_results
                WHERE notification_id = :nid
                ORDER BY created_at ASC
            """),
            {"nid": notification_id},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def get_notification_count(self) -> int:
        count = await self._session.execute(text("SELECT COUNT(*) FROM notifications"))
        return count.scalar() or 0

    async def get_delivery_count(self) -> int:
        count = await self._session.execute(text("SELECT COUNT(*) FROM delivery_results"))
        return count.scalar() or 0
