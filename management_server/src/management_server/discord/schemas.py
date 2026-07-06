"""
Pydantic schemas for the Discord Registration Framework.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegisterGuildRequest(BaseModel):
    """Request to register a Discord guild."""

    guild_id: str = Field(..., description="Discord guild ID")
    name: str = Field(default="", description="Guild name")
    owner_id: str = Field(default="", description="Discord owner user ID")
    paired_machine_uuid: str | None = Field(
        default=None, description="Optional machine UUID to associate"
    )
    pairing_token: str | None = Field(
        default=None, description="Optional pairing token for verification"
    )

    model_config = {"frozen": True}


class RegisterGuildResponse(BaseModel):
    """Response after successful guild registration."""

    guild_id: str
    name: str
    category_name: str
    required_channels: list[dict[str, str]]
    permission_rules: dict[str, Any]
    registered: bool = True
    message: str = ""


class VerifyGuildRequest(BaseModel):
    """Request to verify a guild registration."""

    guild_id: str = Field(..., description="Discord guild ID")
    category_id: str = Field(default="", description="Created category ID")
    channel_ids: dict[str, str] = Field(default_factory=dict, description="Created channel IDs")

    model_config = {"frozen": True}


class VerifyGuildResponse(BaseModel):
    """Response after guild verification."""

    guild_id: str
    verified: bool
    message: str = ""


class GuildConfigResponse(BaseModel):
    """Configuration returned to the Discord Bot."""

    guild_id: str
    category_name: str = "AI Security"
    required_channels: list[dict[str, str]]
    permission_rules: dict[str, Any]
    heartbeat_interval_seconds: int = 30
    notification_channel: str = "critical-alerts"
    notification_preferences: list[dict[str, Any]] = Field(default_factory=list)
    ping_roles: list[dict[str, Any]] = Field(default_factory=list)
    maintenance_mode: bool = False


class GuildInfo(BaseModel):
    """Guild information for API responses."""

    guild_id: str
    name: str
    owner_id: str = ""
    registered_at: datetime | None = None
    verified: bool = False
    active: bool = True
    channel_count: int = 0
    machine_count: int = 0


class GuildDeleteResponse(BaseModel):
    """Response after guild deletion."""

    guild_id: str
    deleted: bool = True
    message: str = ""


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: dict[str, Any] = Field(
        default_factory=lambda: {"code": 500, "message": "Internal server error"}
    )
