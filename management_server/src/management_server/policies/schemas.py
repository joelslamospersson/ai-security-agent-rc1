"""
Pydantic schemas for the Policy Engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FeatureFlagsSchema(BaseModel):
    """Feature flags schema."""

    discord: bool = False
    geoip: bool = False
    docker: bool = False
    web_dashboard: bool = False
    remote_commands: bool = False
    experimental: bool = False


class PolicySchema(BaseModel):
    """Public policy representation."""

    name: str
    description: str = ""
    version: str = "1"
    parent: str = ""
    checksum: str = ""
    heartbeat_interval_seconds: int = 30
    notification_retention_days: int = 30
    log_retention_days: int = 90
    ip_masking_enabled: bool = True
    maintenance_mode: bool = False
    allowed_protocol_versions: list[str] = Field(default_factory=lambda: ["1.0"])
    feature_flags: FeatureFlagsSchema = Field(default_factory=FeatureFlagsSchema)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PolicyListResponse(BaseModel):
    """List of policies."""

    policies: list[PolicySchema]
    total: int


class PolicyAssignRequest(BaseModel):
    """Assign a policy to a machine."""

    machine_uuid: str
    assigned_by: str = "system"


class PolicyOverrideRequest(BaseModel):
    """Override a policy value for a machine."""

    machine_uuid: str
    key: str = Field(
        ..., description="The policy key to override (e.g. heartbeat_interval_seconds)"
    )
    value: Any
    reason: str = ""
    created_by: str = "admin"


class PolicyValidateRequest(BaseModel):
    """Validate a policy YAML payload."""

    name: str
    yaml_content: str


class PolicyValidateResponse(BaseModel):
    """Validation result."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: dict[str, Any] = Field(
        default_factory=lambda: {"code": 500, "message": "Internal server error"}
    )
