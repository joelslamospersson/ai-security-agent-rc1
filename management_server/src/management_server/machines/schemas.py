"""
Pydantic schemas for the machine registry and registration workflow.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from management_server.machines.state_machine import MachineState


class RegistrationRequest(BaseModel):
    """Incoming registration request from a new machine."""

    machine_uuid: str = Field(..., description="Unique machine identifier")
    hostname: str = Field(default="", description="Machine hostname")
    operating_system: str = Field(default="", description="OS identifier")
    architecture: str = Field(default="", description="CPU architecture")
    environment: str = Field(default="production", description="Deployment environment")
    agent_version: str = Field(default="", description="Agent software version")
    public_key_pem: str = Field(..., description="Machine's Ed25519 public key in PEM format")

    model_config = {"frozen": True}


class RegistrationResponse(BaseModel):
    """Response returned after a registration request."""

    machine_uuid: str
    status: MachineState
    message: str = ""
    created_at: datetime | None = None
    certificate_pem: str | None = None


class MachineInfo(BaseModel):
    """Public machine information returned by the API."""

    machine_uuid: str
    hostname: str
    operating_system: str
    architecture: str
    environment: str
    agent_version: str
    public_key_fingerprint: str
    certificate_fingerprint: str
    status: MachineState
    first_seen: datetime | None = None
    approved_at: datetime | None = None
    last_status_change: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ApprovalRequest(BaseModel):
    """Admin approval request."""

    machine_uuid: str
    approved_by: str = Field(default="admin", description="Who approved this machine")
    reason: str = Field(default="", description="Approval justification")


class RejectionRequest(BaseModel):
    """Admin rejection request."""

    machine_uuid: str
    rejected_by: str = Field(default="admin", description="Who rejected this machine")
    reason: str = Field(default="", description="Rejection justification")


class RevocationRequest(BaseModel):
    """Admin revocation request."""

    machine_uuid: str
    revoked_by: str = Field(default="admin", description="Who revoked this machine")
    reason: str = Field(default="", description="Revocation reason")


class MachineListResponse(BaseModel):
    """Paginated list of machines."""

    machines: list[MachineInfo]
    total: int
    page: int = 1
    page_size: int = 100


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: dict[str, Any] = Field(
        default_factory=lambda: {"code": 500, "message": "Internal server error"}
    )
