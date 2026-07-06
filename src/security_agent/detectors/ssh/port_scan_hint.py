"""Port scan correlation hint — emits hints for the Correlation Engine."""

from __future__ import annotations

from typing import Any


class PortScanHintTracker:
    """Provides correlation hints when SSH activity suggests prior scanning.

    If an IP connects to SSH after failing to connect to other ports,
    this tracker emits correlation hints that the Correlation Engine
    uses to build attack chains.
    """

    def __init__(self) -> None:
        self._ssh_connects: set[str] = set()

    def record_ssh(self, ip: str) -> dict[str, Any]:
        self._ssh_connects.add(ip)
        return {
            "detected": False,
            "threat_type": "ssh_connection",
            "source_ip": ip,
            "hint": "port_scan_correlation",
        }

    def has_previous_scan(self, ip: str) -> bool:
        return ip in self._ssh_connects
