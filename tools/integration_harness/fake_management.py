"""
Fake Management Server — simulates the Management Server API for integration testing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from integration_harness.time_controller import TimeController


class FakeManagementServer:
    """Simulates the Management Server REST API.

    Tracks heartbeats, serves pending commands, records audit events.
    """

    def __init__(self, time_controller: TimeController | None = None) -> None:
        self._time = time_controller or TimeController()
        self.heartbeats_received: list[dict[str, Any]] = []
        self.commands_pending: list[dict[str, Any]] = []
        self.audit_events: list[dict[str, Any]] = []
        self.notifications_sent: list[dict[str, Any]] = []
        self.config_versions: dict[str, str] = {}

    async def process_heartbeat(self, heartbeat: dict[str, Any]) -> dict[str, Any]:
        """Process a heartbeat and return a response with pending commands."""
        self.heartbeats_received.append(heartbeat)

        response: dict[str, Any] = {
            "acknowledged": True,
            "negotiated_version": "1.0",
            "configuration_version": self.config_versions.get("config", "0"),
            "rule_version": self.config_versions.get("rules", "0"),
            "policy_version": self.config_versions.get("policies", "0"),
            "maintenance_mode": False,
            "feature_flags": {},
            "pending_commands": list(self.commands_pending),
            "server_timestamp": datetime.fromtimestamp(self._time.now(), tz=UTC).isoformat(),
        }

        # Record audit event for heartbeat
        self.audit_events.append({
            "subsystem": "heartbeat",
            "event_type": "heartbeat",
            "machine_id": heartbeat.get("machine_uuid", ""),
            "description": f"Heartbeat from {heartbeat.get('hostname', 'unknown')}",
            "timestamp": response["server_timestamp"],
        })

        return response

    def add_pending_command(self, command_type: str, machine_id: str = "*",
                            parameters: dict[str, Any] | None = None) -> str:
        """Add a pending command for agents to pick up."""
        cmd_id = uuid4().hex[:16]
        self.commands_pending.append({
            "command_id": cmd_id,
            "command_type": command_type,
            "machine_id": machine_id,
            "parameters": parameters or {},
            "priority": "normal",
        })
        return cmd_id

    def clear_commands(self) -> None:
        """Clear all pending commands."""
        self.commands_pending.clear()

    def set_config_version(self, pkg_type: str, version: str) -> None:
        """Set a configuration version for heartbeat responses."""
        self.config_versions[pkg_type] = version

    @property
    def heartbeat_count(self) -> int:
        return len(self.heartbeats_received)

    @property
    def audit_count(self) -> int:
        return len(self.audit_events)
