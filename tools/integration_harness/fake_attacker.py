"""
Fake Attacker — simulates deterministic attack patterns for testing.
"""

from __future__ import annotations

import random
from typing import Any

from integration_harness.fake_journald import FakeJournald
from integration_harness.time_controller import TimeController


class FakeAttacker:
    """Simulates deterministic attack scenarios for integration testing.

    Every scenario is replayable given the same seed.
    """

    def __init__(
        self,
        seed: int = 42,
        time_controller: TimeController | None = None,
    ) -> None:
        self._rng = random.Random(seed)
        self._time = time_controller or TimeController()
        self._journald = FakeJournald(time_controller)
        self._events: list[dict[str, Any]] = []

    def ssh_brute_force(self, target_ip: str = "10.0.0.1", attempts: int = 100) -> list[dict[str, Any]]:
        """Simulate SSH brute force attack."""
        events: list[dict[str, Any]] = []
        for _ in range(attempts):
            logs = self._journald.generate_ssh_brute_force(1, target_ip)
            for log in logs:
                event = {
                    "attack_type": "ssh_brute_force",
                    "timestamp": log["timestamp"],
                    "source_ip": self._extract_ip(log["message"]),
                    "target_ip": target_ip,
                    "raw_message": log["message"],
                }
                events.append(event)
                self._events.append(event)
        return events

    def password_spraying(self, target_ip: str = "10.0.0.1", users: list[str] | None = None) -> list[dict[str, Any]]:
        """Simulate password spraying across multiple users."""
        if users is None:
            users = ["root", "admin", "ubuntu", "deploy", "test", "www-data"]
        events: list[dict[str, Any]] = []
        for user in users:
            for _ in range(2):
                ip = f"192.168.{self._rng.randint(1, 254)}.{self._rng.randint(1, 254)}"
                msg = f"Failed password for {user} from {ip} port {self._rng.randint(10000, 65000)} ssh2"
                event = {
                    "attack_type": "password_spraying",
                    "timestamp": self._time.now(),
                    "source_ip": ip,
                    "target_ip": target_ip,
                    "target_user": user,
                    "raw_message": msg,
                }
                events.append(event)
                self._events.append(event)
        return events

    def port_scan(self, target_ip: str = "10.0.0.1") -> list[dict[str, Any]]:
        """Simulate port scanning."""
        ports = [22, 80, 443, 3306, 8080, 8443, 27017, 6379, 5432, 9200]
        events: list[dict[str, Any]] = []
        for port in ports:
            event = {
                "attack_type": "port_scan",
                "timestamp": self._time.now(),
                "source_ip": f"10.0.0.{self._rng.randint(2, 10)}",
                "target_ip": target_ip,
                "target_port": port,
                "raw_message": f"Connection attempt on port {port}",
            }
            events.append(event)
            self._events.append(event)
        return events

    def privilege_escalation(self, target_ip: str = "10.0.0.1") -> list[dict[str, Any]]:
        """Simulate privilege escalation indicators."""
        events: list[dict[str, Any]] = [
            {
                "attack_type": "privilege_escalation",
                "timestamp": self._time.now(),
                "source_ip": target_ip,
                "raw_message": "User executed command with elevated privileges: sudo -u root /bin/sh",
            },
            {
                "attack_type": "privilege_escalation",
                "timestamp": self._time.now(),
                "source_ip": target_ip,
                "raw_message": "CVE-2024-XXXX exploitation attempt detected",
            },
        ]
        self._events.extend(events)
        return events

    def _extract_ip(self, message: str) -> str:
        """Extract IP address from log message."""
        parts = message.split()
        for i, part in enumerate(parts):
            if part == "from" and i + 1 < len(parts):
                return parts[i + 1]
        return "unknown"

    def get_all_events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()
