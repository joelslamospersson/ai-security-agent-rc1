"""
Pydantic schemas for the Remote Command Framework.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateCommandRequest(BaseModel):
    """Request to create a new remote command."""

    machine_id: str = Field(..., description="Target machine UUID")
    command_type: str = Field(..., description="Type of command")
    parameters: dict[str, Any] = Field(default_factory=dict)
    priority: str = Field(default="normal", description="Command priority")
    correlation_id: str | None = Field(default=None, description="Optional correlation ID")
    requested_by: str = Field(default="system", description="Who requested this command")
    ttl_hours: int = Field(default=24, ge=1, le=720, description="Hours until expiry")

    model_config = {"frozen": True}


class CommandSchema(BaseModel):
    """Remote command for API responses."""

    command_id: str = ""
    correlation_id: str = ""
    machine_id: str = ""
    command_type: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    priority: str = "normal"
    state: str = "created"
    created_at: datetime | None = None
    expires_at: datetime | None = None
    requested_by: str = "system"


class CommandListResponse(BaseModel):
    """Paginated list of commands."""

    commands: list[CommandSchema]
    total: int


class CancelCommandRequest(BaseModel):
    """Request to cancel a command."""

    reason: str = Field(default="", description="Cancellation reason")
    cancelled_by: str = Field(default="admin", description="Who cancelled")


class AuthorizeCommandRequest(BaseModel):
    """Request to authorize a command."""

    authorized_by: str = Field(default="admin", description="Who authorized")
    reason: str = Field(default="", description="Authorization reason")


class CommandTypeInfo(BaseModel):
    """Information about a supported command type."""

    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: dict[str, Any] = Field(
        default_factory=lambda: {"code": 500, "message": "Internal server error"}
    )
