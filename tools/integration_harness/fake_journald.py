"""
Fake Journald — simulates systemd journal log generation.
"""

from __future__ import annotations

import random
from typing import Any

from integration_harness.time_controller import TimeController


class FakeJournald:
    """Simulates systemd journal entries for agent consumption."""

    SSH_FAILED_PATTERNS = [
        "Failed password for root from {ip} port {port} ssh2",
        "Failed password for admin from {ip} port {port} ssh2",
        "Failed password for invalid user {user} from {ip} port {port} ssh2",
        "Connection closed by authenticating user {user} {ip} port {port}",
        "pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 "
        "tty=ssh ruser= rhost={ip} user={user}",
    ]

    SSH_SUCCESS_PATTERN = "Accepted password for {user} from {ip} port {port} ssh2"

    def __init__(self, time_controller: TimeController | None = None) -> None:
        self._time = time_controller or TimeController()
        self._logs: list[dict[str, Any]] = []

    def generate_ssh_brute_force(self, count: int = 10, target_ip: str = "10.0.0.1") -> list[dict[str, Any]]:
        """Generate SSH brute force log entries."""
        entries: list[dict[str, Any]] = []
        for _ in range(count):
            ip = f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
            port = random.randint(10000, 65000)
            user = random.choice(["root", "admin", "ubuntu", "test", "deploy"])
            pattern = random.choice(self.SSH_FAILED_PATTERNS)
            msg = pattern.format(ip=ip, port=port, user=user)
            entry = {
                "timestamp": self._time.now(),
                "source": "sshd",
                "message": msg,
                "priority": 4,  # warning
            }
            entries.append(entry)
            self._logs.append(entry)
        return entries

    def generate_ssh_success(self, ip: str = "10.0.0.1", user: str = "admin") -> dict[str, Any]:
        """Generate a single SSH success entry."""
        port = random.randint(10000, 65000)
        msg = self.SSH_SUCCESS_PATTERN.format(ip=ip, port=port, user=user)
        entry = {
            "timestamp": self._time.now(),
            "source": "sshd",
            "message": msg,
            "priority": 5,  # notice
        }
        self._logs.append(entry)
        return entry

    def generate_port_scan(self, target_ip: str = "10.0.0.1") -> list[dict[str, Any]]:
        """Generate port scan detection entries."""
        entries: list[dict[str, Any]] = []
        for port in [22, 80, 443, 3306, 8080, 8443, 27017]:
            entry = {
                "timestamp": self._time.now(),
                "source": "kernel",
                "message": f"SYN flood detected from {target_ip} to port {port}",
                "priority": 3,  # error
            }
            entries.append(entry)
            self._logs.append(entry)
        return entries

    def get_recent(self, count: int = 100) -> list[dict[str, Any]]:
        """Get most recent log entries."""
        return self._logs[-count:]

    def clear(self) -> None:
        """Clear all generated logs."""
        self._logs.clear()
