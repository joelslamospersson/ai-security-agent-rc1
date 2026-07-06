"""
Pipeline Engine — orchestrates event processing through stages.

The Pipeline Engine receives events from the Event Bus, creates a
PipelineContext for each event, and runs the event through all
registered stages in order. Each stage returns a ProcessingResult
that tells the engine how to proceed.

Key guarantees:
- One failed stage never crashes the engine
- Retry logic is deterministic and configurable
- Pipeline cancellation is clean and immediate
- All metrics are tracked for observability
- Context propagation preserves correlation IDs across stages
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from security_agent.event_bus.bus import EventBus
from security_agent.events.envelope import EventEnvelope
from security_agent.events.event_types import EventType
from security_agent.events.models import BaseEvent
from security_agent.pipeline.context import PipelineContext, StageTiming
from security_agent.pipeline.metrics import (
    PipelineMetricsCollector,
    PipelineMetricsSnapshot,
)
from security_agent.pipeline.registry import StageRegistry
from security_agent.pipeline.result import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    ProcessingResult,
)
from security_agent.pipeline.stage import PipelineStage

logger = logging.getLogger("pipeline")


class PipelineEngine:
    """Orchestrates event processing through pipeline stages.

    Flow:
    1. Subscribe to Event Bus for relevant event types.
    2. For each received event, create PipelineContext.
    3. Run event through all enabled stages in registry order.
    4. React to each stage's ProcessingResult.
    5. Record metrics and timing for every stage execution.

    Usage:
        engine = PipelineEngine(event_bus, registry)
        await engine.start()
        # ... events flow through stages ...
        await engine.shutdown()
    """

    def __init__(
        self,
        event_bus: EventBus,
        registry: StageRegistry,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._bus = event_bus
        self._registry = registry
        self._config = config or {}
        self._metrics = PipelineMetricsCollector()
        self._subscriptions: list[Any] = []
        self._shutting_down = False
        self._started = False

        self._max_retries = self._config.get("max_retries", DEFAULT_MAX_RETRIES)
        self._retry_delay = self._config.get("retry_delay", DEFAULT_RETRY_DELAY)
        self._subscribe_events: list[EventType] = self._config.get(
            "subscribe_events",
            [EventType.SECURITY_EVENT],
        )

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> None:
        """Start the Pipeline Engine.

        Subscribes to configured Event Types and initializes all stages.
        """
        if self._started:
            return

        # Initialize all registered stages
        stages = self._registry.get_all_stages()
        for stage in stages:
            try:
                await stage.initialize()
                logger.info(
                    "Stage initialized",
                    extra={"stage": stage.name},
                )
            except Exception as e:
                logger.error(
                    "Stage initialization failed",
                    extra={"stage": stage.name, "error": str(e)},
                )
                # Disable the stage so the pipeline continues without it
                self._registry.disable(stage.name)

        # Subscribe to the Event Bus
        for event_type in self._subscribe_events:
            sub = self._bus.subscribe(
                event_type,
                self._handle_event,
                name=f"pipeline-{event_type.name}",
            )
            self._subscriptions.append(sub)

        self._started = True
        enabled_count = self._registry.enabled_count
        logger.info(
            "Pipeline Engine started",
            extra={
                "stages_enabled": enabled_count,
                "stages_total": self._registry.total_count,
                "subscribe_events": [e.name for e in self._subscribe_events],
            },
        )

    async def shutdown(self) -> None:
        """Shut down the Pipeline Engine.

        Unsubscribes from the Event Bus and shuts down all stages.
        """
        if self._shutting_down:
            return
        self._shutting_down = True

        # Unsubscribe from Event Bus
        for sub in self._subscriptions:
            self._bus.unsubscribe(sub)
        self._subscriptions.clear()

        # Shut down all stages in reverse order
        stages = self._registry.get_all_stages()
        for stage in reversed(stages):
            try:
                await stage.shutdown()
                logger.debug(
                    "Stage shut down",
                    extra={"stage": stage.name},
                )
            except Exception as e:
                logger.error(
                    "Stage shutdown error",
                    extra={"stage": stage.name, "error": str(e)},
                )

        self._started = False
        logger.info("Pipeline Engine shut down")

    # =========================================================================
    # Event handling
    # =========================================================================

    async def _handle_event(self, envelope: EventEnvelope) -> None:
        """Handle an incoming event from the Event Bus.

        Creates a PipelineContext and runs the event through
        all enabled stages.
        """
        if self._shutting_down:
            return

        event = envelope.event
        context = PipelineContext(
            correlation_id=event.correlation_id,
        )

        self._metrics.pipeline_started()
        pipeline_start = time.monotonic()
        queue_wait = pipeline_start - envelope.publish_ts.timestamp()
        self._metrics.record_queue_wait(max(0, queue_wait))

        try:
            await self._run_pipeline(event, context)
        except Exception as e:
            logger.error(
                "Pipeline execution error",
                extra={
                    "correlation_id": context.correlation_id,
                    "error": str(e),
                },
                exc_info=True,
            )
        finally:
            pipeline_latency = time.monotonic() - pipeline_start
            self._metrics.record_pipeline_latency(pipeline_latency)
            self._metrics.pipeline_finished()

    async def _run_pipeline(
        self,
        event: BaseEvent,
        context: PipelineContext,
    ) -> None:
        """Run an event through all enabled stages."""
        stages = self._registry.get_enabled_stages()

        for stage in stages:
            if context.cancelled:
                self._metrics.increment_cancelled()
                logger.debug(
                    "Pipeline cancelled",
                    extra={
                        "correlation_id": context.correlation_id,
                        "stage": stage.name,
                    },
                )
                return

            context.current_stage = stage.name
            result = await self._execute_stage(stage, event, context)

            if result == ProcessingResult.DROP:
                self._metrics.increment_dropped()
                logger.debug(
                    "Event dropped by stage",
                    extra={
                        "correlation_id": context.correlation_id,
                        "stage": stage.name,
                    },
                )
                return

            if result == ProcessingResult.STOP:
                logger.info(
                    "Pipeline stopped by stage",
                    extra={
                        "correlation_id": context.correlation_id,
                        "stage": stage.name,
                    },
                )
                return

            if result == ProcessingResult.ERROR:
                self._metrics.increment_failed()
                logger.error(
                    "Pipeline error from stage",
                    extra={
                        "correlation_id": context.correlation_id,
                        "stage": stage.name,
                    },
                )
                return

            # CONTINUE: proceed to next stage
            self._metrics.increment_processed()

        logger.debug(
            "Pipeline complete",
            extra={
                "correlation_id": context.correlation_id,
                "stages": len(stages),
                "latency_ms": round(context.elapsed_ms, 1),
            },
        )

    async def _execute_stage(
        self,
        stage: PipelineStage,
        event: BaseEvent,
        context: PipelineContext,
    ) -> ProcessingResult:
        """Execute a single stage with retry support."""
        max_retries = self._max_retries

        for attempt in range(max_retries + 1):
            timing = StageTiming(stage_name=stage.name, start_time=time.monotonic())

            try:
                result = await stage.process(event, context)
                timing.end_time = time.monotonic()
                timing.duration_ms = (timing.end_time - timing.start_time) * 1000
                timing.retry_count = attempt
                timing.result = result.name
                context.record_timing(timing)

                self._metrics.record_stage_latency(
                    stage.name, timing.duration_ms / 1000
                )

                if result == ProcessingResult.RETRY and attempt < max_retries:
                    context.increment_retry(stage.name)
                    self._metrics.increment_retries()
                    delay = self._retry_delay * (2**attempt)  # exponential backoff
                    logger.debug(
                        "Retrying stage",
                        extra={
                            "stage": stage.name,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay_ms": round(delay * 1000),
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

                if result == ProcessingResult.RETRY:
                    return ProcessingResult.ERROR
                return result

            except Exception as e:
                timing.end_time = time.monotonic()
                timing.duration_ms = (timing.end_time - timing.start_time) * 1000
                timing.result = "EXCEPTION"
                context.record_timing(timing)

                self._metrics.record_stage_latency(
                    stage.name, timing.duration_ms / 1000
                )

                if attempt < max_retries:
                    context.increment_retry(stage.name)
                    self._metrics.increment_retries()
                    delay = self._retry_delay * (2**attempt)
                    logger.warning(
                        "Stage exception, retrying",
                        extra={
                            "stage": stage.name,
                            "attempt": attempt + 1,
                            "error": str(e),
                            "delay_ms": round(delay * 1000),
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.error(
                    "Stage failed after retries",
                    extra={
                        "stage": stage.name,
                        "attempts": attempt + 1,
                        "error": str(e),
                    },
                    exc_info=True,
                )
                return ProcessingResult.ERROR

        return ProcessingResult.ERROR

    # =========================================================================
    # Metrics
    # =========================================================================

    def metrics_snapshot(self) -> PipelineMetricsSnapshot:
        """Return current pipeline metrics snapshot."""
        return self._metrics.snapshot(
            stage_names=self._registry.stage_names,
        )

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    @property
    def stage_count(self) -> int:
        return int(self._registry.enabled_count)
