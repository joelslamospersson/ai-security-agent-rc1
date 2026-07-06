"""
Pydantic schemas for the heartbeat protocol.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentHealthSchema(BaseModel):
    """Agent-side health metrics."""

    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    disk_percent: float = 0.0
    load_average: float = 0.0
    agent_uptime_seconds: float = 0.0
    host_uptime_seconds: float = 0.0


class AgentCapabilitiesSchema(BaseModel):
    """Advertised agent capabilities."""

    iptables: bool = False
    sqlite: bool = False
    ssh_detector: bool = False
    geoip: bool = False
    fail2ban: bool = False
    docker: bool = False
    feature_flags: dict[str, bool] = Field(default_factory=dict)


class QueueMetricsSchema(BaseModel):
    """Agent queue depths."""

    event_queue: int = 0
    detection_queue: int = 0
    firewall_queue: int = 0


class AgentSecuritySchema(BaseModel):
    """Agent security posture indicators."""

    current_posture: str = "unknown"
    trust_indicators: dict[str, Any] = Field(default_factory=dict)
    configuration_hash: str = ""
    rule_hash: str = ""
    binary_hash: str = ""


class HeartbeatRequestSchema(BaseModel):
    """Incoming heartbeat from an agent."""

    machine_uuid: str = Field(..., description="Unique machine identifier")
    certificate_fingerprint: str = Field(default="", description="Machine certificate fingerprint")
    protocol_version: str = Field(default="1.0", description="Heartbeat protocol version")
    agent_version: str = Field(default="", description="Agent software version")
    hostname: str = Field(default="", description="Machine hostname")
    environment: str = Field(default="production", description="Deployment environment")
    timestamp: datetime | None = Field(default=None, description="Agent-side timestamp")
    sequence_number: int = Field(default=0, ge=0, description="Monotonic sequence number")
    capabilities: AgentCapabilitiesSchema | None = None
    health: AgentHealthSchema | None = None
    queues: QueueMetricsSchema | None = None
    security: AgentSecuritySchema | None = None

    model_config = {"frozen": True}


class HeartbeatResponseSchema(BaseModel):
    """Response returned to the agent after a heartbeat."""

    acknowledged: bool = True
    negotiated_version: str = ""
    configuration_version: str = "0"
    rule_version: str = "0"
    policy_version: str = "0"
    maintenance_mode: bool = False
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    pending_commands: list[dict[str, Any]] = Field(default_factory=list)
    server_timestamp: datetime = Field(default_factory=datetime.now)


class MachineStatusSchema(BaseModel):
    """Machine online status for API responses."""

    machine_uuid: str
    status: str
    hostname: str = ""
    protocol_version: str = ""
    agent_version: str = ""
    last_heartbeat: datetime | None = None
    environment: str = ""
    capabilities: list[str] = Field(default_factory=list)


class HeartbeatMetricsSchema(BaseModel):
    """Heartbeat metrics snapshot for API."""

    heartbeats_received: int = 0
    heartbeats_missed: int = 0
    protocol_errors: int = 0
    version_mismatches: int = 0
    capability_changes: int = 0
    average_latency_ms: float = 0.0
    online_machines: int = 0
    offline_machines: int = 0
    delayed_machines: int = 0


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: dict[str, Any] = Field(
        default_factory=lambda: {"code": 500, "message": "Internal server error"}
    )
