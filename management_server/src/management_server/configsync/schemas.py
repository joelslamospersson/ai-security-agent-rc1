"""
Pydantic schemas for the Configuration Synchronization Framework.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreatePackageRequest(BaseModel):
    """Request to create a new configuration package."""

    package_type: str = Field(..., description="Type of package")
    version: str = Field(default="1", description="Package version")
    payload: str = Field(default="", description="Package payload content")
    metadata: dict[str, Any] = Field(default_factory=dict)
    minimum_agent_version: str = Field(default="", description="Minimum required agent version")
    rollback_version: str = Field(default="", description="Previous version for rollback")
    format_type: str = Field(default="full", description="full or delta")
    base_package_id: str = Field(default="", description="Base package ID for deltas")

    model_config = {"frozen": True}


class PackageSchema(BaseModel):
    """Configuration package for API responses."""

    package_id: str = ""
    package_type: str = ""
    version: str = "1"
    format: str = "full"
    state: str = "created"
    checksum: str = ""
    signature: str = ""
    minimum_agent_version: str = ""
    rollback_version: str = ""
    created_at: datetime | None = None


class PackageListResponse(BaseModel):
    """Paginated list of packages."""

    packages: list[PackageSchema]
    total: int


class PublishRequest(BaseModel):
    """Request to publish a package."""

    package_id: str = Field(..., description="Package to publish")
    published_by: str = Field(default="admin", description="Who published")


class MachineVersionSchema(BaseModel):
    """Machine version state for a package type."""

    machine_uuid: str
    package_type: str
    current_version: str = "0"
    desired_version: str = ""
    last_sync_at: datetime | None = None


class AvailablePackageSchema(BaseModel):
    """Package advertised in heartbeat response."""

    package_id: str
    package_type: str
    version: str
    format: str
    checksum: str
    minimum_agent_version: str = ""
    rollback_version: str = ""


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: dict[str, Any] = Field(
        default_factory=lambda: {"code": 500, "message": "Internal server error"}
    )
