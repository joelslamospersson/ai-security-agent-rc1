"""
Heartbeat and machine status models.

Machine status lifecycle:
    HEALTHY → DELAYED → OFFLINE → RECOVERED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Any


class MachineStatus(StrEnum):
    """Online state of a managed machine."""

    HEALTHY = auto()
    DELAYED = auto()
    OFFLINE = auto()
    RECOVERED = auto()
    UNKNOWN = auto()


class ProtocolVersion(StrEnum):
    """Supported heartbeat protocol versions."""

    V1 = "1.0"

    @classmethod
    def latest(cls) -> ProtocolVersion:
        return cls.V1

    @classmethod
    def supported_versions(cls) -> list[str]:
        return [v.value for v in cls]

    @classmethod
    def is_supported(cls, version: str) -> bool:
        return version in cls.supported_versions()

    @staticmethod
    def negotiate(agent_version: str, server_version: str | None = None) -> str:
        """Negotiate the highest mutually supported protocol version."""
        if server_version is None:
            server_version = ProtocolVersion.latest().value
        if agent_version == server_version:
            return agent_version
        if ProtocolVersion.is_supported(agent_version):
            return agent_version
        if ProtocolVersion.is_supported(server_version):
            return server_version
        return ""


@dataclass
class AgentHealth:
    """Agent-side health metrics."""

    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    disk_percent: float = 0.0
    load_average: float = 0.0
    agent_uptime_seconds: float = 0.0
    host_uptime_seconds: float = 0.0


@dataclass
class AgentCapabilities:
    """Advertised agent capabilities."""

    iptables: bool = False
    sqlite: bool = False
    ssh_detector: bool = False
    geoip: bool = False
    fail2ban: bool = False
    docker: bool = False
    feature_flags: dict[str, bool] = field(default_factory=dict)


@dataclass
class QueueMetrics:
    """Agent queue depths."""

    event_queue: int = 0
    detection_queue: int = 0
    firewall_queue: int = 0


@dataclass
class AgentSecurity:
    """Agent security posture indicators."""

    current_posture: str = "unknown"
    trust_indicators: dict[str, Any] = field(default_factory=dict)
    configuration_hash: str = ""
    rule_hash: str = ""
    binary_hash: str = ""


@dataclass
class HeartbeatRequest:
    """Incoming heartbeat from an agent."""

    machine_uuid: str = ""
    certificate_fingerprint: str = ""
    protocol_version: str = ""
    agent_version: str = ""
    hostname: str = ""
    environment: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    sequence_number: int = 0
    capabilities: AgentCapabilities | None = None
    health: AgentHealth | None = None
    queues: QueueMetrics | None = None
    security: AgentSecurity | None = None


@dataclass
class HeartbeatResponse:
    """Response returned to the agent after a heartbeat."""

    acknowledged: bool = True
    negotiated_version: str = ""
    configuration_version: str = "0"
    rule_version: str = "0"
    policy_version: str = "0"
    maintenance_mode: bool = False
    feature_flags: dict[str, bool] = field(default_factory=dict)
    pending_commands: list[dict[str, Any]] = field(default_factory=list)
    server_timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass
class HeartbeatRecord:
    """Persistent record of a received heartbeat."""

    machine_uuid: str = ""
    protocol_version: str = ""
    agent_version: str = ""
    hostname: str = ""
    environment: str = ""
    status: MachineStatus = MachineStatus.HEALTHY
    sequence_number: int = 0
    received_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    health_json: str = ""
    capabilities_json: str = ""
    queues_json: str = ""
    security_json: str = ""


@dataclass
class TimeoutConfig:
    """Configurable heartbeat timeout thresholds."""

    healthy_timeout_seconds: int = 30
    delayed_timeout_seconds: int = 120
    offline_timeout_seconds: int = 300

    def get_status(self, seconds_since_last_heartbeat: float) -> MachineStatus:
        if seconds_since_last_heartbeat <= self.healthy_timeout_seconds:
            return MachineStatus.HEALTHY
        if seconds_since_last_heartbeat <= self.delayed_timeout_seconds:
            return MachineStatus.DELAYED
        if seconds_since_last_heartbeat <= self.offline_timeout_seconds:
            return MachineStatus.OFFLINE
        return MachineStatus.OFFLINE
