"""
Benchmark — measures system performance during harness execution.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from integration_harness.fake_agent import FakeAgent
from integration_harness.metrics import MetricsCollector


class Benchmark:
    """Runs performance benchmarks against simulated components."""

    def __init__(self, metrics: MetricsCollector | None = None) -> None:
        self._metrics = metrics or MetricsCollector()
        self._results: dict[str, Any] = {}

    async def run_all(self, iterations: int = 100) -> dict[str, Any]:
        """Run all benchmarks."""
        self._results["heartbeat_throughput"] = await self._benchmark_heartbeat(iterations)
        self._results["startup"] = await self._benchmark_startup()
        self._results["shutdown"] = await self._benchmark_shutdown()
        return self._results

    async def _benchmark_heartbeat(self, count: int) -> dict[str, Any]:
        """Benchmark heartbeat processing throughput."""
        agent = FakeAgent()
        latencies: list[float] = []

        for _ in range(count):
            hb = agent.create_heartbeat()
            t = time.monotonic()
            # Simulate processing
            _ = hb.get("machine_uuid", "")
            elapsed = (time.monotonic() - t) * 1000
            latencies.append(elapsed)
            self._metrics.record_latency("heartbeat", elapsed)

        return {
            "count": count,
            "avg_ms": round(sum(latencies) / len(latencies), 2),
            "min_ms": round(min(latencies), 2),
            "max_ms": round(max(latencies), 2),
            "throughput_per_second": round(count / (sum(latencies) / 1000), 0),
        }

    async def _benchmark_startup(self) -> dict[str, Any]:
        """Benchmark simulated startup time."""
        t = time.monotonic()
        agent = FakeAgent()
        _ = agent.create_heartbeat()
        elapsed = time.monotonic() - t
        self._metrics.metrics.startup_time = elapsed
        return {"seconds": round(elapsed, 4)}

    async def _benchmark_shutdown(self) -> dict[str, Any]:
        """Benchmark simulated shutdown time."""
        t = time.monotonic()
        await asyncio.sleep(0.001)  # Simulate cleanup
        elapsed = time.monotonic() - t
        self._metrics.metrics.shutdown_time = elapsed
        return {"seconds": round(elapsed, 4)}
