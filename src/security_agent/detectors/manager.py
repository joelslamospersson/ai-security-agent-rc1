"""
DetectorManager — lifecycle management for all detectors.

Responsibilities:
- Initialize and shut down detectors
- Route events to compatible detectors
- Isolate detector failures
- Collect metrics
- Manage enable/disable state
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from security_agent.detectors.context import DetectorContext
from security_agent.detectors.metrics import (
    DetectorMetricsCollector,
    DetectorMetricsSnapshot,
)
from security_agent.detectors.registry import DetectorRegistry
from security_agent.detectors.result import DetectionResult
from security_agent.events.models import BaseEvent

logger = logging.getLogger("detectors")


class DetectorManager:
    """Manages lifecycle and execution of all detectors.

    Usage:
        manager = DetectorManager(registry, config)
        await manager.initialize_all()
        results = await manager.analyze(event)
        await manager.shutdown_all()
    """

    def __init__(
        self,
        registry: DetectorRegistry,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._registry = registry
        self._config = config or {}
        self._metrics = DetectorMetricsCollector()
        self._initialized = False

    async def initialize_all(self) -> None:
        """Initialize all registered detectors.

        Failed initializations are logged; the detector is disabled.
        A failing detector never blocks others.
        """
        detectors = self._registry.list_all()
        for detector in detectors:
            try:
                await detector.initialize()
                logger.info(
                    "Detector initialized",
                    extra={
                        "detector": detector.name,
                        "id": detector.detector_id,
                    },
                )
            except Exception as e:
                logger.error(
                    "Detector initialization failed",
                    extra={
                        "detector": detector.name,
                        "error": str(e),
                    },
                )
                self._registry.disable(detector.name)

        self._initialized = True
        logger.info(
            "Detector initialization complete",
            extra={
                "registered": self._registry.count,
                "enabled": len(self._registry.list_enabled()),
            },
        )

    async def shutdown_all(self) -> None:
        """Shut down all detectors in reverse registration order."""
        detectors = list(reversed(self._registry.list_enabled()))
        for detector in detectors:
            try:
                await detector.shutdown()
            except Exception as e:
                logger.error(
                    "Detector shutdown error",
                    extra={
                        "detector": detector.name,
                        "error": str(e),
                    },
                )
        logger.info("All detectors shut down")

    async def analyze(
        self,
        event: BaseEvent,
        correlation_id: str = "",
    ) -> list[DetectionResult]:
        """Analyze an event with all compatible enabled detectors.

        Detectors that cannot process this event (based on capabilities)
        are skipped without error. Failing detectors are isolated.
        """
        all_results: list[DetectionResult] = []
        detectors = self._registry.list_enabled()
        category = getattr(event, "category", None)
        event_type = getattr(event, "event_type", None)

        for detector in detectors:
            caps = detector.capabilities()

            # Skip if detector cannot process this event
            if (
                event_type is not None
                and caps.event_types
                and event_type not in caps.event_types
            ):
                self._metrics.event_skipped()
                continue
            if (
                category is not None
                and caps.event_categories
                and category not in caps.event_categories
            ):
                self._metrics.event_skipped()
                continue

            # Build context
            ctx = DetectorContext(
                settings=self._config.get(detector.name, {}),
                logger=logging.getLogger(f"detectors.{detector.name}"),
                event_metadata=getattr(event, "metadata", {}),
                correlation_id=correlation_id,
            )

            # Execute detector
            start = time.monotonic()
            try:
                results = await detector.analyze(event, ctx)
                elapsed = time.monotonic() - start
                self._metrics.record_latency(elapsed)
                self._metrics.event_analyzed()

                if results:
                    self._metrics.detections(len(results))
                    all_results.extend(results)

                if elapsed > 1.0:
                    logger.warning(
                        "Slow detector",
                        extra={
                            "detector": detector.name,
                            "latency_ms": round(elapsed * 1000),
                        },
                    )

            except asyncio.CancelledError:
                raise
            except Exception as e:
                elapsed = time.monotonic() - start
                self._metrics.analysis_failed()
                self._metrics.record_latency(elapsed)
                logger.error(
                    "Detector analysis failed",
                    extra={
                        "detector": detector.name,
                        "error": str(e),
                    },
                    exc_info=True,
                )

        return all_results

    # =========================================================================
    # Metrics
    # =========================================================================

    def metrics_snapshot(self) -> DetectorMetricsSnapshot:
        return self._metrics.snapshot(
            registered=self._registry.count,
            enabled=len(self._registry.list_enabled()),
            names=self._registry.names,
        )

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def is_initialized(self) -> bool:
        return self._initialized
