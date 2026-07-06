"""
JournaldMonitor — subscribes to systemd-journald and publishes normalized events.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import Any

from security_agent.events import EventType, SecurityEvent
from security_agent.monitors import Monitor
from security_agent.monitors.base import HealthState
from security_agent.monitors.context import MonitorContext
from security_agent.monitors.filters import JournalFilter
from security_agent.monitors.journal_reader import JournalReader, JournalReaderState
from security_agent.monitors.normalizer import JournalNormalizer

logger = logging.getLogger("journald.monitor")


class JournaldMonitor(Monitor):  # type: ignore[misc]
    """Monitor that reads from systemd-journald and publishes normalized events."""

    def __init__(
        self,
        name: str = "journald",
        units: list[str] | None = None,
        identifiers: list[str] | None = None,
        priority: str = "info",
    ) -> None:
        super().__init__(name)
        self._units = units or []
        self._identifiers = identifiers or []
        self._priority = priority
        self._reader = None
        self._normalizer = None
        self._filter_obj = None
        self._read_task = None
        self._publish_count = 0
        self._filtered_count = 0
        self._normalize_count = 0
        self._last_read_time = 0.0

    async def initialize(self, ctx: MonitorContext) -> None:
        await super().initialize(ctx)
        config = ctx.settings
        self._filter_obj = JournalFilter.from_config(config.get("filter", {}))
        units = self._units or config.get("units", [])
        idents = self._identifiers or config.get("identifiers", [])
        priority = config.get("priority", self._priority)
        self._reader = JournalReader(
            filter_obj=self._filter_obj,
            units=units,
            identifiers=idents,
            priority=priority,
        )
        self._normalizer = JournalNormalizer()
        logger.info(
            "Journald monitor initialized",
            extra={"units": units, "identifiers": idents},
        )

    async def start(self) -> None:
        if self._reader is None or self._normalizer is None:
            raise RuntimeError("Monitor not initialized")
        await super().start()
        self._read_task = asyncio.create_task(self._read_loop())
        logger.info("Journald monitor started")

    async def stop(self) -> None:
        if self._read_task is not None:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None
        if self._reader is not None:
            await self._reader.close()
        await super().stop()
        logger.info(
            "Journald monitor stopped", extra={"published": self._publish_count}
        )

    async def _read_loop(self) -> None:
        if self._reader is None or self._normalizer is None:
            return
        publisher = self.context.publisher if self.context else None
        if publisher is None:
            logger.error("No publisher available")
            return
        try:
            async for raw_entry in self._reader.read():
                self._last_read_time = time.monotonic()
                if self._filter_obj is not None and not self._filter_obj.matches(
                    raw_entry
                ):
                    self._filtered_count += 1
                    self._increment_events()
                    continue
                try:
                    normalized = self._normalizer.normalize(raw_entry)
                    self._normalize_count += 1
                except Exception as e:
                    logger.error("Normalization failed", extra={"error": str(e)})
                    self._record_failure(f"normalization: {e}")
                    continue
                try:
                    event = SecurityEvent(
                        correlation_id=normalized.correlation_id,
                        source="journald",
                        severity=normalized.priority or 0,
                        raw_message=normalized.message,
                        metadata={
                            "pid": normalized.pid,
                            "uid": normalized.uid,
                            "executable": normalized.executable,
                            "systemd_unit": normalized.systemd_unit,
                            "identifier": normalized.identifier,
                            "transport": normalized.transport,
                            "priority": normalized.priority,
                            "facility": normalized.facility,
                        },
                    )
                    await publisher.publish(EventType.SECURITY_EVENT, event)
                    self._publish_count += 1
                    self._increment_events()
                except Exception as e:
                    logger.error("Publish failed", extra={"error": str(e)})
                    self._record_failure(f"publish: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Read loop error", extra={"error": str(e)})
            self._record_failure(f"read_loop: {e}")

    def health(self) -> Any:
        report = super().health()
        if self._reader is not None:
            rs = self._reader.state
            if rs == JournalReaderState.CONNECTED:
                report.status = HealthState.HEALTHY
            elif rs == JournalReaderState.RECONNECTING:
                report.status = HealthState.DEGRADED
            elif rs == JournalReaderState.DISCONNECTED:
                report.status = HealthState.FAILED
        report.metadata.update(
            {
                "publish_count": self._publish_count,
                "filtered_count": self._filtered_count,
                "normalize_count": self._normalize_count,
                "reconnect_count": self._reader.reconnect_count if self._reader else 0,
                "reader_state": self._reader.state if self._reader else "N/A",
            }
        )
        return report

    def capabilities(self) -> dict[str, Any]:
        return {"journald": True, "native_bindings": bool(sys.modules.get("systemd"))}
