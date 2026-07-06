"""
Fake AI Security Agent — simulates an agent sending heartbeats, processing
commands, and generating security events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from integration_harness.fake_journald import FakeJournald
from integration_harness.time_controller import TimeController

FAKE_MACHINE_UUID = "00000000-0000-0000-0000-000000000001"
FAKE_CERT_FINGERPRINT = "a1b2c3d4e5f6" * 4


class FakeAgent:
    """Simulates an AI Security Agent for integration testing."""

    def __init__(
        self,
        machine_uuid: str = FAKE_MACHINE_UUID,
        hostname: str = "test-agent-01",
        time_controller: TimeController | None = None,
    ) -> None:
        self.machine_uuid = machine_uuid
        self.hostname = hostname
        self._time = time_controller or TimeController()
        self._journald = FakeJournald(time_controller)
        self._sequence = 0
        self._commands: list[dict[str, Any]] = []
        self._responses: list[dict[str, Any]] = []

    def create_heartbeat(
        self,
        event_queue_size: int = 0,
        detection_queue_size: int = 0,
        cpu_percent: float = 25.0,
        ram_percent: float = 50.0,
    ) -> dict[str, Any]:
        """Create a heartbeat request as the Management Server expects."""
        self._sequence += 1
        return {
            "machine_uuid": self.machine_uuid,
            "certificate_fingerprint": FAKE_CERT_FINGERPRINT,
            "protocol_version": "1.0",
            "agent_version": "2.0.0",
            "hostname": self.hostname,
            "environment": "production",
            "timestamp": datetime.fromtimestamp(self._time.now(), tz=UTC).isoformat(),
            "sequence_number": self._sequence,
            "capabilities": {
                "iptables": True,
                "sqlite": True,
                "ssh_detector": True,
                "geoip": False,
                "fail2ban": True,
                "docker": False,
            },
            "health": {
                "cpu_percent": cpu_percent,
                "ram_percent": ram_percent,
                "disk_percent": 35.0,
                "load_average": 1.2,
                "agent_uptime_seconds": 86400,
                "host_uptime_seconds": 604800,
            },
            "queues": {
                "event_queue": event_queue_size,
                "detection_queue": detection_queue_size,
                "firewall_queue": 0,
            },
            "security": {
                "current_posture": "secured",
                "trust_indicators": {"binary_integrity": True, "config_integrity": True},
                "configuration_hash": "abc123",
                "rule_hash": "def456",
                "binary_hash": "789abc",
            },
        }

    def generate_ssh_brute_force_events(self, count: int = 5) -> list[dict[str, Any]]:
        """Generate SSH brute force security events as the agent would."""
        logs = self._journald.generate_ssh_brute_force(count)
        events: list[dict[str, Any]] = []
        for log in logs:
            events.append({
                "event_type": "ssh_failed_login",
                "timestamp": log["timestamp"],
                "source": log["message"].split()[-3] if "from" in log["message"] else "unknown",
                "raw_message": log["message"],
            })
        return events

    def record_command_response(self, command_id: str, status: str = "acknowledged") -> dict[str, Any]:
        """Record a command acknowledgement for the heartbeat."""
        resp = {
            "command_id": command_id,
            "status": status,
            "timestamp": datetime.fromtimestamp(self._time.now(), tz=UTC).isoformat(),
        }
        self._responses.append(resp)
        return resp

    def get_pending_acks(self) -> list[dict[str, Any]]:
        """Get pending command acknowledgements."""
        acks = list(self._responses)
        self._responses.clear()
        return acks
