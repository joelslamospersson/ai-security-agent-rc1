"""
Pydantic schemas for the Audit Engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEventSchema(BaseModel):
    """Audit event for API responses."""

    audit_id: str = ""
    correlation_id: str = ""
    timestamp: datetime | None = None
    machine_id: str = ""
    subsystem: str = ""
    actor: str = "system"
    event_type: str = ""
    severity: str = "info"
    outcome: str = "success"
    description: str = ""
    metadata_json: str = "{}"
    current_hash: str = ""
    previous_hash: str = ""


class AuditVerifyResponse(BaseModel):
    """Response from integrity verification."""

    verified: bool
    total_events: int = 0
    verified_events: int = 0
    failed_events: int = 0
    first_failure_id: str = ""


class AuditExportRequest(BaseModel):
    """Request to export audit events."""

    format: str = Field(default="json", pattern="^(json|csv|parquet)$")
    start_date: datetime | None = None
    end_date: datetime | None = None
    subsystem: str | None = None
    event_type: str | None = None


class AuditExportResponse(BaseModel):
    """Response from export request."""

    format: str
    event_count: int
    filename: str
    size_bytes: int


class AuditListResponse(BaseModel):
    """Paginated list of audit events."""

    events: list[AuditEventSchema]
    total: int


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: dict[str, Any] = Field(
        default_factory=lambda: {"code": 500, "message": "Internal server error"}
    )
