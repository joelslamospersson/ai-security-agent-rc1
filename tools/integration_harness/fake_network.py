"""
Fake Network — simulates network conditions: latency, partitions, failures.
"""

from __future__ import annotations

import random
from typing import Any


class FakeNetwork:
    """Simulates network conditions for integration testing."""

    def __init__(self) -> None:
        self._latency_ms: float = 0.0
        self._packet_loss: float = 0.0
        self._partitioned: bool = False
        self._partitioned_hosts: set[str] = set()

    def set_latency(self, ms: float) -> None:
        """Simulate network latency in milliseconds."""
        self._latency_ms = ms

    def set_packet_loss(self, percentage: float) -> None:
        """Simulate packet loss (0.0 to 1.0)."""
        self._packet_loss = percentage

    def partition(self, host: str | None = None) -> None:
        """Partition the network (optionally isolate a host)."""
        self._partitioned = True
        if host:
            self._partitioned_hosts.add(host)

    def heal(self) -> None:
        """Restore network connectivity."""
        self._partitioned = False
        self._partitioned_hosts.clear()

    async def simulate_request(self, target: str = "") -> dict[str, Any]:
        """Simulate a network request with current conditions."""
        if self._partitioned:
            if not target or target in self._partitioned_hosts or not self._partitioned_hosts:
                return {"success": False, "error": "network_partition", "latency_ms": 0.0}

        if random.random() < self._packet_loss:
            return {"success": False, "error": "packet_loss", "latency_ms": 0.0}

        return {"success": True, "latency_ms": self._latency_ms}

    @property
    def is_healthy(self) -> bool:
        return not self._partitioned and self._packet_loss == 0.0
