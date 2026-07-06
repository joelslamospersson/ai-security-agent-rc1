"""
Notification API endpoints for the Management Server.

GET    /api/v1/notifications                  — List notifications
GET    /api/v1/notifications/{notification_id} — Get notification
GET    /api/v1/notifications/queue              — Get queue depth
POST   /api/v1/notifications/preview            — Preview notification
POST   /api/v1/notifications/replay             — Replay from routing decision
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from management_server.notifications.manager import NotificationManager
from management_server.notifications.schemas import (
    ErrorResponse,
    NotificationPreviewRequest,
    NotificationPreviewResponse,
    NotificationReplayRequest,
    NotificationSchema,
    QueueDepthSchema,
)

router = APIRouter(prefix="/api/v1", tags=["notifications"])


async def _get_notification_manager(request: Request) -> NotificationManager:
    mgr: NotificationManager | None = getattr(request.app.state, "notification_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Notification manager not initialized")
    return mgr


@router.get(
    "/notifications",
    summary="List notifications",
)
async def list_notifications(
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    manager: NotificationManager = Depends(_get_notification_manager),  # noqa: B008
) -> dict[str, Any]:
    """List recent notifications."""
    result: dict[str, Any] = await manager.list_notifications(limit=limit, offset=offset)
    return result


@router.get(
    "/notifications/{notification_id}",
    response_model=NotificationSchema,
    responses={404: {"model": ErrorResponse}},
    summary="Get a notification",
)
async def get_notification(
    notification_id: str,
    manager: NotificationManager = Depends(_get_notification_manager),  # noqa: B008
) -> NotificationSchema:
    """Get a specific notification by ID."""
    notification = await manager.get_notification(notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail=f"Notification not found: {notification_id}")
    return notification


@router.get(
    "/notifications/queue",
    response_model=QueueDepthSchema,
    summary="Get notification queue depth",
)
async def get_queue_depth(
    manager: NotificationManager = Depends(_get_notification_manager),  # noqa: B008
) -> dict[str, int]:
    """Get the current depth of each notification priority queue."""
    result: dict[str, int] = await manager.get_queue_depth()
    return result


@router.post(
    "/notifications/preview",
    response_model=NotificationPreviewResponse,
    summary="Preview a notification",
)
async def preview_notification(
    body: NotificationPreviewRequest,
    manager: NotificationManager = Depends(_get_notification_manager),  # noqa: B008
) -> NotificationPreviewResponse:
    """Preview formatted notification output without persisting."""
    return await manager.preview(
        event_type=body.event_type,
        destination=body.destination,
        template=body.template,
        metadata=body.metadata,
    )


@router.post(
    "/notifications/replay",
    summary="Replay notifications",
)
async def replay_notifications(
    body: NotificationReplayRequest,
    manager: NotificationManager = Depends(_get_notification_manager),  # noqa: B008
) -> list[NotificationSchema]:
    """Recreate notifications from a routing decision. No delivery."""
    result: list[NotificationSchema] = await manager.replay(
        routing_decision_id=body.routing_decision_id,
        destinations=body.destinations,
    )
    return result
