"""
Pydantic schemas for the secure pairing protocol.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from management_server.pairing.models import TokenState


class PairingTokenCreateRequest(BaseModel):
    """Request to generate a new pairing token."""

    creator: str = Field(default="system", description="Who or what created this token")
    ttl_minutes: int = Field(default=15, ge=1, le=1440, description="Token lifetime in minutes")
    machine_uuid: str | None = Field(default=None, description="Optional pre-assigned machine")
    audit_reference: str = Field(default="", description="External audit reference")

    model_config = {"frozen": True}


class PairingTokenResponse(BaseModel):
    """Response returned after token generation.

    The `token` value is the plaintext 64-byte secure token.
    It is returned exactly once and never stored.
    """

    token: str
    token_id: str
    expires_at: datetime
    status: TokenState = TokenState.ISSUED

    model_config = {"frozen": True}


class PairingValidateRequest(BaseModel):
    """Request to validate a pairing token."""

    token: str = Field(..., min_length=1, description="The plaintext pairing token")
    machine_uuid: str = Field(..., description="The machine presenting the token")

    model_config = {"frozen": True}


class PairingValidateResponse(BaseModel):
    """Response after successful token validation."""

    valid: bool
    token_id: str
    status: TokenState
    message: str = ""


class PairingConsumeRequest(BaseModel):
    """Request to consume a pairing token and complete pairing."""

    token: str = Field(..., min_length=1, description="The plaintext pairing token")
    machine_uuid: str = Field(..., description="The machine to pair")

    model_config = {"frozen": True}


class PairingConsumeResponse(BaseModel):
    """Response after successful token consumption."""

    paired: bool
    machine_uuid: str
    token_id: str
    message: str = ""


class PairingInfo(BaseModel):
    """Public pairing token info (no hash, no plaintext)."""

    token_id: str
    status: TokenState
    creator: str
    machine_uuid: str | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    consumed_at: datetime | None = None
    audit_reference: str = ""


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: dict[str, Any] = Field(
        default_factory=lambda: {"code": 500, "message": "Internal server error"}
    )
