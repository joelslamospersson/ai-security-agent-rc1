"""
Pydantic schemas for the Notification Engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NotificationSchema(BaseModel):
    """Notification for API responses."""

    notification_id: str = ""
    routing_decision_id: str = ""
    machine_id: str = ""
    event_type: str = ""
    destination: str = ""
    priority: str = "normal"
    template: str = "detailed"
    payload: str = ""
    status: str = "pending"
    created_at: datetime | None = None


class NotificationPreviewRequest(BaseModel):
    """Request to preview a notification."""

    event_type: str = Field(..., description="Event type for template")
    destination: str = Field(default="console", description="Target destination")
    template: str = Field(default="detailed", description="Formatter template")
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class NotificationPreviewResponse(BaseModel):
    """Preview of a formatted notification."""

    template: str
    payload: str
    estimated_size_bytes: int


class NotificationReplayRequest(BaseModel):
    """Request to replay notifications from a routing decision."""

    routing_decision_id: str = Field(..., description="Source routing decision ID")
    destinations: list[str] | None = Field(default=None, description="Override destinations")

    model_config = {"frozen": True}


class NotificationListResponse(BaseModel):
    """Paginated list of notifications."""

    notifications: list[NotificationSchema]
    total: int


class QueueDepthSchema(BaseModel):
    """Queue depth information."""

    immediate: int = 0
    high: int = 0
    normal: int = 0
    low: int = 0
    bulk: int = 0


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: dict[str, Any] = Field(
        default_factory=lambda: {"code": 500, "message": "Internal server error"}
    )
