"""
Pydantic schemas for the Routing Engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EventToRoute(BaseModel):
    """An incoming event that needs a routing decision."""

    machine_id: str = Field(..., description="Machine that produced the event")
    event_type: str = Field(..., description="Type of event")
    severity: str = Field(default="info", description="Event severity")
    machine_state: str = Field(default="healthy", description="Current machine state")
    environment: str = Field(default="production", description="Machine environment")
    policy: str = Field(default="default", description="Assigned policy")
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class RoutingDecisionSchema(BaseModel):
    """Immutable routing decision for API responses."""

    decision_id: str
    timestamp: datetime | None = None
    machine_id: str = ""
    event_type: str = ""
    destinations: list[str] = Field(default_factory=list)
    priority: str = "normal"
    template: str = "detailed"
    rate_limit_profile: str = "normal"
    retention_policy: str = "standard"
    matched_rule: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoutingRuleSchema(BaseModel):
    """Routing rule for API display."""

    name: str
    description: str = ""
    event_types: list[str] = Field(default_factory=lambda: ["*"])
    destinations: list[str] = Field(default_factory=list)
    priority: str = "normal"
    template: str = "detailed"
    enabled: bool = True


class RoutingConfigReloadResponse(BaseModel):
    """Response after reloading routing config."""

    rules_loaded: int
    profiles_loaded: int
    errors: list[str] = Field(default_factory=list)


class RoutingEvaluateResponse(BaseModel):
    """Response after evaluating an event."""

    decision: RoutingDecisionSchema
    matched: bool = True


class RoutingDecisionListResponse(BaseModel):
    """List of routing decisions."""

    decisions: list[RoutingDecisionSchema]
    total: int


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: dict[str, Any] = Field(
        default_factory=lambda: {"code": 500, "message": "Internal server error"}
    )
