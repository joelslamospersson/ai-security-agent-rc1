"""
Heartbeat protocol — version negotiation, request building, response building.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from management_server.heartbeat.exceptions import ProtocolMismatchError
from management_server.heartbeat.models import (
    AgentCapabilities,
    AgentHealth,
    AgentSecurity,
    HeartbeatRequest,
    HeartbeatResponse,
    QueueMetrics,
)
from management_server.heartbeat.schemas import HeartbeatRequestSchema

logger = structlog.get_logger("heartbeat.protocol")

SUPPORTED_VERSIONS = ["1.0"]
LATEST_VERSION = "1.0"


class HeartbeatProtocol:
    """Heartbeat protocol handler — version negotiation and message building."""

    def __init__(self) -> None:
        self._supported_versions: dict[str, int] = {
            "1.0": 1,
        }

    def negotiate_version(self, agent_version: str) -> str:
        """Negotiate protocol version.

        Returns the negotiated version string.
        Raises ProtocolMismatchError if versions are incompatible.
        """
        if agent_version in self._supported_versions:
            return agent_version

        # Try latest supported
        if LATEST_VERSION in self._supported_versions:
            logger.warning(
                "Protocol version fallback",
                agent_version=agent_version,
                negotiated=LATEST_VERSION,
            )
            return LATEST_VERSION

        raise ProtocolMismatchError(
            int(agent_version.split(".")[0]),
            int(LATEST_VERSION.split(".")[0]),
        )

    def parse_request(self, payload: HeartbeatRequestSchema) -> HeartbeatRequest:
        """Convert a validated schema to an internal HeartbeatRequest."""
        return HeartbeatRequest(
            machine_uuid=payload.machine_uuid,
            certificate_fingerprint=payload.certificate_fingerprint,
            protocol_version=payload.protocol_version,
            agent_version=payload.agent_version,
            hostname=payload.hostname,
            environment=payload.environment,
            timestamp=payload.timestamp or datetime.now(tz=UTC),
            sequence_number=payload.sequence_number,
            capabilities=self._parse_capabilities(payload.capabilities),
            health=self._parse_health(payload.health),
            queues=self._parse_queues(payload.queues),
            security=self._parse_security(payload.security),
        )

    def build_response(
        self,
        _request: HeartbeatRequest,
        negotiated_version: str,
        configuration_version: str = "0",
        rule_version: str = "0",
        policy_version: str = "0",
        maintenance_mode: bool = False,
        feature_flags: dict[str, bool] | None = None,
        pending_commands: list[dict[str, Any]] | None = None,
    ) -> HeartbeatResponse:
        """Build a heartbeat response for an agent."""
        return HeartbeatResponse(
            acknowledged=True,
            negotiated_version=negotiated_version,
            configuration_version=configuration_version,
            rule_version=rule_version,
            policy_version=policy_version,
            maintenance_mode=maintenance_mode,
            feature_flags=feature_flags or {},
            pending_commands=pending_commands or [],
            server_timestamp=datetime.now(tz=UTC),
        )

    def response_to_dict(self, response: HeartbeatResponse) -> dict[str, Any]:
        """Convert HeartbeatResponse to a dict for JSON serialization."""
        return {
            "acknowledged": response.acknowledged,
            "negotiated_version": response.negotiated_version,
            "configuration_version": response.configuration_version,
            "rule_version": response.rule_version,
            "policy_version": response.policy_version,
            "maintenance_mode": response.maintenance_mode,
            "feature_flags": response.feature_flags,
            "pending_commands": response.pending_commands,
            "server_timestamp": response.server_timestamp.isoformat(),
        }

    def detect_capability_changes(
        self,
        old_caps: dict[str, bool] | None,
        new_caps: dict[str, bool] | None,
    ) -> list[dict[str, Any]]:
        """Detect capability changes between two snapshots.

        Returns a list of change events.
        """
        changes: list[dict[str, Any]] = []
        old = old_caps or {}
        new = new_caps or {}

        all_keys = set(old.keys()) | set(new.keys())
        for key in sorted(all_keys):
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val is None and new_val is not None:
                changes.append({"capability": key, "change": "added", "value": new_val})
            elif old_val is not None and new_val is None:
                changes.append({"capability": key, "change": "removed", "value": None})
            elif old_val != new_val:
                changes.append(
                    {
                        "capability": key,
                        "change": "changed",
                        "old_value": old_val,
                        "new_value": new_val,
                    }
                )
        return changes

    @staticmethod
    def _parse_capabilities(
        schema: Any,
    ) -> AgentCapabilities | None:
        if schema is None:
            return None
        return AgentCapabilities(
            iptables=getattr(schema, "iptables", False),
            sqlite=getattr(schema, "sqlite", False),
            ssh_detector=getattr(schema, "ssh_detector", False),
            geoip=getattr(schema, "geoip", False),
            fail2ban=getattr(schema, "fail2ban", False),
            docker=getattr(schema, "docker", False),
            feature_flags=getattr(schema, "feature_flags", {}),
        )

    @staticmethod
    def _parse_health(schema: Any) -> AgentHealth | None:
        if schema is None:
            return None
        return AgentHealth(
            cpu_percent=getattr(schema, "cpu_percent", 0.0),
            ram_percent=getattr(schema, "ram_percent", 0.0),
            disk_percent=getattr(schema, "disk_percent", 0.0),
            load_average=getattr(schema, "load_average", 0.0),
            agent_uptime_seconds=getattr(schema, "agent_uptime_seconds", 0.0),
            host_uptime_seconds=getattr(schema, "host_uptime_seconds", 0.0),
        )

    @staticmethod
    def _parse_queues(schema: Any) -> QueueMetrics | None:
        if schema is None:
            return None
        return QueueMetrics(
            event_queue=getattr(schema, "event_queue", 0),
            detection_queue=getattr(schema, "detection_queue", 0),
            firewall_queue=getattr(schema, "firewall_queue", 0),
        )

    @staticmethod
    def _parse_security(schema: Any) -> AgentSecurity | None:
        if schema is None:
            return None
        return AgentSecurity(
            current_posture=getattr(schema, "current_posture", "unknown"),
            trust_indicators=getattr(schema, "trust_indicators", {}),
            configuration_hash=getattr(schema, "configuration_hash", ""),
            rule_hash=getattr(schema, "rule_hash", ""),
            binary_hash=getattr(schema, "binary_hash", ""),
        )
