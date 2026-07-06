"""
MonitorManager — lifecycle management for all monitors.

Responsibilities:
- Start monitors in registration order
- Stop monitors in reverse order
- Track health of all running monitors
- Publish monitor lifecycle events to the Event Bus
- Isolate monitor failures
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from security_agent.event_bus import EventBus
from security_agent.monitors.base import Monitor
from security_agent.monitors.context import MonitorContext
from security_agent.monitors.events import (
    monitor_failed,
    monitor_started,
    monitor_stopped,
)
from security_agent.monitors.metrics import (
    MonitorMetricsCollector,
    MonitorMetricsSnapshot,
)
from security_agent.monitors.registry import MonitorRegistry

logger = logging.getLogger("monitors")


def _publish_safe(bus: EventBus, event: Any, publisher: str) -> None:
    """Safely publish an event, catching and logging errors."""
    try:
        task = asyncio.create_task(
            bus.publish(event.event_type, event, publisher=publisher)
        )
        task.add_done_callback(lambda _: None)  # Suppress RUF006
    except Exception:
        logger.exception("Failed to publish monitor event")


class MonitorManager:
    """Manages lifecycle, health, and isolation of all monitors.

    Usage:
        manager = MonitorManager(event_bus, registry)
        await manager.initialize_all()
        await manager.start_all()
        ...
        await manager.stop_all()
    """

    def __init__(
        self,
        event_bus: EventBus,
        registry: MonitorRegistry,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._bus = event_bus
        self._registry = registry
        self._config = config or {}
        self._metrics = MonitorMetricsCollector()
        self._started: bool = False
        self._shutting_down: bool = False

    async def initialize_all(self) -> None:
        """Initialize all enabled monitors in registration order."""
        monitors = self._registry.list_enabled()
        for monitor in monitors:
            try:
                ctx = MonitorContext(
                    name=monitor.name,
                    settings=self._config.get(monitor.name, {}),
                    event_bus=self._bus,
                    publisher=self._bus.create_publisher(f"monitor.{monitor.name}"),
                    logger=logging.getLogger(f"monitors.{monitor.name}"),
                )
                await monitor.initialize(ctx)
                logger.info("Monitor initialized", extra={"monitor": monitor.name})
            except Exception as e:
                logger.error(
                    "Monitor initialization failed",
                    extra={"monitor": monitor.name, "error": str(e)},
                )
                self._registry.disable(monitor.name)
                _publish_safe(
                    self._bus, monitor_failed(monitor.name, str(e)), "manager"
                )

    async def start_all(self) -> None:
        """Start all initialized monitors concurrently."""
        monitors = self._registry.list_enabled()
        start_time = time.monotonic()

        async def start_one(monitor: Monitor) -> None:
            try:
                await monitor.start()
                self._metrics.monitor_started()
                _publish_safe(self._bus, monitor_started(monitor.name), "manager")
                logger.info("Monitor started", extra={"monitor": monitor.name})
            except Exception as e:
                self._metrics.monitor_failed()
                self._registry.disable(monitor.name)
                _publish_safe(
                    self._bus, monitor_failed(monitor.name, str(e)), "manager"
                )
                logger.error(
                    "Monitor start failed",
                    extra={"monitor": monitor.name, "error": str(e)},
                )

        tasks = [asyncio.create_task(start_one(m)) for m in monitors]
        await asyncio.gather(*tasks)
        self._metrics.record_startup_time(time.monotonic() - start_time)
        self._started = True

    async def stop_all(self) -> None:
        """Stop all monitors in reverse registration order."""
        if self._shutting_down:
            return
        self._shutting_down = True

        monitors = list(reversed(self._registry.list_enabled()))
        stop_time = time.monotonic()

        for monitor in monitors:
            try:
                await monitor.stop()
                self._metrics.monitor_stopped()
                _publish_safe(self._bus, monitor_stopped(monitor.name), "manager")
                logger.info("Monitor stopped", extra={"monitor": monitor.name})
            except Exception as e:
                logger.error(
                    "Monitor stop error",
                    extra={"monitor": monitor.name, "error": str(e)},
                )

        self._metrics.record_shutdown_time(time.monotonic() - stop_time)
        self._started = False
        self._shutting_down = False

    def health_report(self) -> dict[str, Any]:
        """Return health report for all monitors."""
        report: dict[str, Any] = {}
        for monitor in self._registry.list_all():
            try:
                h = monitor.health()
                report[monitor.name] = {
                    "status": h.status.name,
                    "uptime": h.uptime,
                    "last_error": h.last_error,
                    "enabled": self._registry.is_enabled(monitor.name),
                }
            except Exception:
                report[monitor.name] = {"status": "ERROR", "enabled": False}
        return report

    def metrics_snapshot(self) -> MonitorMetricsSnapshot:
        """Return current metrics snapshot."""
        return self._metrics.snapshot(
            registered=self._registry.count,
            enabled=self._registry.enabled_count,
            disabled=self._registry.count - self._registry.enabled_count,
            names=self._registry.names,
        )

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def running_count(self) -> int:
        return int(self._metrics.snapshot().running_monitors)
