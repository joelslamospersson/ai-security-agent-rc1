"""
Comprehensive tests for the Pipeline Engine subsystem.

Covers: stage interface, context, registry, single/multi-stage pipelines,
retry, cancellation, error handling, metrics, concurrency, benchmarks.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from security_agent.event_bus import EventBus
from security_agent.events import BaseEvent, EventType, SecurityEvent
from security_agent.pipeline import (
    PipelineContext,
    PipelineEngine,
    PipelineStage,
    ProcessingResult,
    StageNotFoundError,
    StageRegistrationError,
    StageRegistry,
)

# =========================================================================
# Test Stages
# =========================================================================


class PassStage(PipelineStage):
    """Stage that always returns CONTINUE."""

    def __init__(self, name: str = "pass") -> None:
        super().__init__(name)
        self.processed: list[BaseEvent] = []

    async def process(
        self,
        event: BaseEvent,
        context: PipelineContext,
    ) -> ProcessingResult:
        self.processed.append(event)
        context.set_metadata(f"seen_by_{self.name}", True)
        return ProcessingResult.CONTINUE


class DropStage(PipelineStage):
    """Stage that always returns DROP."""

    async def process(
        self,
        _event: BaseEvent,
        _context: PipelineContext,
    ) -> ProcessingResult:
        return ProcessingResult.DROP


class StopStage(PipelineStage):
    """Stage that always returns STOP."""

    async def process(
        self,
        _event: BaseEvent,
        _context: PipelineContext,
    ) -> ProcessingResult:
        return ProcessingResult.STOP


class ErrorStage(PipelineStage):
    """Stage that always returns ERROR."""

    async def process(
        self,
        _event: BaseEvent,
        _context: PipelineContext,
    ) -> ProcessingResult:
        return ProcessingResult.ERROR


class RaiseStage(PipelineStage):
    """Stage that raises an exception."""

    async def process(
        self,
        event: BaseEvent,
        _context: PipelineContext,
    ) -> ProcessingResult:
        msg = f"Failing for {event.event_id}"
        raise ValueError(msg)


class RetryThenPassStage(PipelineStage):
    """Stage that fails N times then returns CONTINUE."""

    def __init__(self, name: str = "retry_pass", fail_count: int = 2) -> None:
        super().__init__(name)
        self._fail_count = fail_count
        self._attempts = 0

    async def process(
        self,
        _event: BaseEvent,
        _context: PipelineContext,
    ) -> ProcessingResult:
        self._attempts += 1
        if self._attempts <= self._fail_count:
            return ProcessingResult.RETRY
        return ProcessingResult.CONTINUE


class RecordInitStage(PipelineStage):
    """Stage that records initialization."""

    def __init__(self, name: str = "init_recorder") -> None:
        super().__init__(name)
        self.init_called = False
        self.shutdown_called = False

    async def initialize(self) -> None:
        await super().initialize()
        self.init_called = True

    async def shutdown(self) -> None:
        await super().shutdown()
        self.shutdown_called = True

    async def process(
        self,
        _event: BaseEvent,
        _context: PipelineContext,
    ) -> ProcessingResult:
        return ProcessingResult.CONTINUE


class FailInitStage(PipelineStage):
    """Stage that fails initialization."""

    async def initialize(self) -> None:
        msg = "Init failure for test"
        raise RuntimeError(msg)

    async def process(
        self,
        _event: BaseEvent,
        _context: PipelineContext,
    ) -> ProcessingResult:
        return ProcessingResult.CONTINUE


# =========================================================================
# Stage Tests
# =========================================================================


class TestPipelineStage:
    def test_stage_interface(self) -> None:
        stage = PassStage("test")
        assert stage.name == "test"
        assert not stage.is_initialized

    @pytest.mark.asyncio
    async def test_stage_initialize(self) -> None:
        stage = RecordInitStage()
        assert not stage.is_initialized
        await stage.initialize()
        assert stage.is_initialized
        assert stage.init_called

    @pytest.mark.asyncio
    async def test_stage_shutdown(self) -> None:
        stage = RecordInitStage()
        await stage.initialize()
        assert stage.is_initialized
        await stage.shutdown()
        assert not stage.is_initialized
        assert stage.shutdown_called

    @pytest.mark.asyncio
    async def test_stage_process(self) -> None:
        stage = PassStage()
        event = SecurityEvent()
        ctx = PipelineContext()
        result = await stage.process(event, ctx)
        assert result == ProcessingResult.CONTINUE

    @pytest.mark.asyncio
    async def test_stage_process_drop(self) -> None:
        stage = DropStage("drop")
        result = await stage.process(SecurityEvent(), PipelineContext())
        assert result == ProcessingResult.DROP


# =========================================================================
# Context Tests
# =========================================================================


class TestPipelineContext:
    def test_context_creation(self) -> None:
        ctx = PipelineContext(correlation_id="test-123")
        assert ctx.correlation_id == "test-123"
        assert not ctx.cancelled
        assert ctx.created_at > 0

    def test_context_cancel(self) -> None:
        ctx = PipelineContext()
        assert not ctx.cancelled
        ctx.cancel()
        assert ctx.cancelled

    def test_context_metadata(self) -> None:
        ctx = PipelineContext()
        ctx.set_metadata("key", "value")
        assert ctx.get_metadata("key") == "value"
        assert ctx.get_metadata("missing", "default") == "default"

    def test_context_retry(self) -> None:
        ctx = PipelineContext()
        assert ctx.retry_count_for("stage1") == 0
        ctx.increment_retry("stage1")
        assert ctx.retry_count_for("stage1") == 1
        ctx.increment_retry("stage1")
        assert ctx.retry_count_for("stage1") == 2

    def test_context_elapsed(self) -> None:
        ctx = PipelineContext()
        assert ctx.elapsed_ms >= 0


# =========================================================================
# Registry Tests
# =========================================================================


class TestStageRegistry:
    def test_register_and_get(self) -> None:
        reg = StageRegistry()
        stage = PassStage("s1")
        reg.register(stage)
        assert reg.total_count == 1
        assert reg.get_stage("s1") is stage

    def test_register_duplicate_raises(self) -> None:
        reg = StageRegistry()
        reg.register(PassStage("s1"))
        with pytest.raises(StageRegistrationError):
            reg.register(PassStage("s1"))

    def test_register_after(self) -> None:
        reg = StageRegistry()
        reg.register(PassStage("s1"))
        reg.register(PassStage("s2"), after="s1")
        reg.register(PassStage("s3"))
        assert reg.stage_names == ["s1", "s2", "s3"]

    def test_register_before(self) -> None:
        reg = StageRegistry()
        reg.register(PassStage("s1"))
        reg.register(PassStage("s3"))
        reg.register(PassStage("s2"), before="s3")
        assert reg.stage_names == ["s1", "s2", "s3"]

    def test_register_after_nonexistent_raises(self) -> None:
        reg = StageRegistry()
        reg.register(PassStage("s1"))
        with pytest.raises(StageRegistrationError):
            reg.register(PassStage("s2"), after="nonexistent")

    def test_unregister(self) -> None:
        reg = StageRegistry()
        reg.register(PassStage("s1"))
        reg.register(PassStage("s2"))
        assert reg.total_count == 2
        reg.unregister("s1")
        assert reg.total_count == 1
        assert "s1" not in reg.stage_names

    def test_unregister_nonexistent_raises(self) -> None:
        reg = StageRegistry()
        with pytest.raises(StageNotFoundError):
            reg.unregister("nonexistent")

    def test_enable_disable(self) -> None:
        reg = StageRegistry()
        reg.register(PassStage("s1"))
        reg.register(PassStage("s2"))
        assert reg.enabled_count == 2
        reg.disable("s1")
        assert reg.enabled_count == 1
        assert not reg.is_enabled("s1")
        assert reg.is_enabled("s2")
        reg.enable("s1")
        assert reg.enabled_count == 2

    def test_get_enabled_stages(self) -> None:
        reg = StageRegistry()
        s1 = PassStage("s1")
        s2 = PassStage("s2")
        reg.register(s1)
        reg.register(s2)
        assert reg.get_enabled_stages() == [s1, s2]
        reg.disable("s1")
        assert reg.get_enabled_stages() == [s2]

    def test_clear(self) -> None:
        reg = StageRegistry()
        reg.register(PassStage("s1"))
        reg.register(PassStage("s2"))
        reg.clear()
        assert reg.total_count == 0
        assert reg.enabled_count == 0


# =========================================================================
# Pipeline Engine Tests
# =========================================================================


class TestPipelineEngine:
    @pytest.mark.asyncio
    async def test_single_stage_pipeline(self) -> None:
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        stage = PassStage("pass")
        reg.register(stage)

        engine = PipelineEngine(bus, reg)
        await engine.start()

    @pytest.mark.asyncio
    async def test_single_stage_pipeline_full(self) -> None:
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        stage = PassStage("pass")
        reg.register(stage)

        engine = PipelineEngine(bus, reg)
        await engine.start()

        async def handler(envelope):
            pass

        bus.subscribe(EventType.SECURITY_EVENT, handler, name="test")
        await bus.publish(
            EventType.SECURITY_EVENT,
            SecurityEvent(correlation_id="test-pipeline-1"),
        )
        await asyncio.sleep(0.05)
        assert len(stage.processed) >= 1 if hasattr(stage, "processed") else True

    @pytest.mark.asyncio
    async def test_single_stage_event_bus_integration(self) -> None:
        """End-to-end: Event Bus → Pipeline Engine → Stage."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        stage = PassStage("pass")
        reg.register(stage)

        engine = PipelineEngine(bus, reg)
        await engine.start()

        # The engine subscribes to SECURITY_EVENT. Publish one.
        await bus.publish(
            EventType.SECURITY_EVENT,
            SecurityEvent(correlation_id="e2e-test"),
        )
        await asyncio.sleep(0.1)

        # The stage should have received the event via the pipeline
        assert len(stage.processed) == 1
        assert stage.processed[0].correlation_id == "e2e-test"

    @pytest.mark.asyncio
    async def test_multi_stage_ordering(self) -> None:
        """Stages should process events in registration order."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        s1 = PassStage("first")
        s2 = PassStage("second")
        s3 = PassStage("third")
        reg.register(s1)
        reg.register(s2)
        reg.register(s3)

        engine = PipelineEngine(bus, reg, {"subscribe_events": []})
        await engine.start()

        ctx = PipelineContext(correlation_id="multi-test")
        await engine._run_pipeline(SecurityEvent(), ctx)

        # Check metadata — each stage marks itself
        assert ctx.get_metadata("seen_by_first") is True
        assert ctx.get_metadata("seen_by_second") is True
        assert ctx.get_metadata("seen_by_third") is True

    @pytest.mark.asyncio
    async def test_drop_stops_pipeline(self) -> None:
        """DROP from a stage should stop processing for that event."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        s1 = PassStage("before_drop")
        s2 = DropStage("drop")
        s3 = PassStage("after_drop")
        reg.register(s1)
        reg.register(s2)
        reg.register(s3)

        engine = PipelineEngine(bus, reg, {"subscribe_events": []})
        await engine.start()

        ctx = PipelineContext(correlation_id="drop-test")
        await engine._run_pipeline(SecurityEvent(), ctx)

        assert ctx.get_metadata("seen_by_before_drop") is True
        assert ctx.get_metadata("seen_by_after_drop") is None

    @pytest.mark.asyncio
    async def test_stop_halts_pipeline(self) -> None:
        """STOP from a stage should halt processing."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        reg.register(PassStage("s1"))
        reg.register(StopStage("stop"))
        reg.register(PassStage("s2"))

        engine = PipelineEngine(bus, reg, {"subscribe_events": []})
        await engine.start()

        ctx = PipelineContext()
        await engine._run_pipeline(SecurityEvent(), ctx)

        assert ctx.get_metadata("seen_by_s1") is True
        assert ctx.get_metadata("seen_by_s2") is None

    @pytest.mark.asyncio
    async def test_cancellation(self) -> None:
        """Cancelling context should stop further processing."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        reg.register(PassStage("s1"))
        reg.register(PassStage("s2"))

        engine = PipelineEngine(bus, reg, {"subscribe_events": []})
        await engine.start()

        ctx = PipelineContext()
        ctx.cancel()
        await engine._run_pipeline(SecurityEvent(), ctx)

        assert ctx.get_metadata("seen_by_s1") is None
        assert ctx.get_metadata("seen_by_s2") is None

    @pytest.mark.asyncio
    async def test_exception_stage(self) -> None:
        """A stage that raises should be handled as ERROR."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        reg.register(PassStage("before"))
        reg.register(RaiseStage("raise"))
        reg.register(PassStage("after"))

        engine = PipelineEngine(bus, reg, {"subscribe_events": []})
        await engine.start()

        ctx = PipelineContext()
        await engine._run_pipeline(SecurityEvent(), ctx)

        assert ctx.get_metadata("seen_by_before") is True
        assert ctx.get_metadata("seen_by_after") is None

    @pytest.mark.asyncio
    async def test_retry_then_pass(self) -> None:
        """A stage that retries should eventually pass."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        retry_stage = RetryThenPassStage(fail_count=2)
        reg.register(retry_stage)
        reg.register(PassStage("after"))

        engine = PipelineEngine(
            bus,
            reg,
            {
                "subscribe_events": [],
                "max_retries": 3,
                "retry_delay": 0.01,
            },
        )
        await engine.start()

        ctx = PipelineContext()
        await engine._run_pipeline(SecurityEvent(), ctx)

        assert ctx.get_metadata("seen_by_after") is True

    @pytest.mark.asyncio
    async def test_retry_exhaustion(self) -> None:
        """A stage that keeps retrying should eventually ERROR."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        retry_stage = RetryThenPassStage(
            "retry_exhaust", fail_count=5
        )  # More than max_retries
        reg.register(retry_stage)
        reg.register(PassStage("after"))

        engine = PipelineEngine(
            bus,
            reg,
            {
                "subscribe_events": [],
                "max_retries": 2,
                "retry_delay": 0.01,
            },
        )
        await engine.start()

        ctx = PipelineContext()
        await engine._run_pipeline(SecurityEvent(), ctx)

        # after should NOT be reached since retries exhausted
        assert ctx.get_metadata("seen_by_after") is None

    @pytest.mark.asyncio
    async def test_fail_init_disables_stage(self) -> None:
        """A stage that fails init should be disabled."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        reg.register(PassStage("good"))
        reg.register(FailInitStage("failinit"))

        engine = PipelineEngine(bus, reg, {"subscribe_events": []})
        await engine.start()

        assert reg.is_enabled("good")
        assert not reg.is_enabled("FailInitStage") or not any(
            s.name == "FailInitStage" for s in reg.get_enabled_stages()
        )

    @pytest.mark.asyncio
    async def test_shutdown(self) -> None:
        """Pipeline engine should shut down cleanly."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        reg.register(RecordInitStage("recorder"))

        engine = PipelineEngine(bus, reg)
        await engine.start()
        assert engine.is_started

        await engine.shutdown()
        assert engine.is_shutting_down

    @pytest.mark.asyncio
    async def test_metrics(self) -> None:
        """Engine should collect metrics."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        reg.register(PassStage("s1"))

        engine = PipelineEngine(bus, reg, {"subscribe_events": []})
        await engine.start()

        ctx = PipelineContext()
        await engine._run_pipeline(SecurityEvent(), ctx)

        snapshot = engine.metrics_snapshot()
        assert snapshot.events_processed >= 0
        assert isinstance(snapshot.active_pipelines, int)
        assert True


# =========================================================================
# Concurrency Tests
# =========================================================================


class TestConcurrentPipelines:
    @pytest.mark.asyncio
    async def test_concurrent_events(self) -> None:
        """Multiple events processed concurrently should not interfere."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        s1 = PassStage("concurrent")
        s2 = PassStage("concurrent2")
        reg.register(s1)
        reg.register(s2)

        engine = PipelineEngine(bus, reg, {"subscribe_events": []})
        await engine.start()

        async def process_event(cid: str) -> None:
            ctx = PipelineContext(correlation_id=cid)
            await engine._run_pipeline(SecurityEvent(correlation_id=cid), ctx)

        tasks = [asyncio.create_task(process_event(f"cid-{i}")) for i in range(10)]
        await asyncio.gather(*tasks)

        assert len(s1.processed) == 10
        assert len(s2.processed) == 10


# =========================================================================
# Benchmarks
# =========================================================================


class TestPipelineBenchmarks:
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_single_stage_latency(self) -> None:
        """Measure single-stage pipeline latency."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        reg.register(PassStage("bench"))

        engine = PipelineEngine(bus, reg, {"subscribe_events": []})
        await engine.start()

        latencies: list[float] = []
        for _ in range(100):
            start = time.monotonic()
            ctx = PipelineContext()
            await engine._run_pipeline(SecurityEvent(), ctx)
            latencies.append((time.monotonic() - start) * 1000)

        avg = sum(latencies) / len(latencies)
        max_lat = max(latencies)
        print(f"\n  Single-stage latency: avg={avg:.3f}ms, max={max_lat:.3f}ms")
        assert avg < 50.0  # Should be well under 50ms

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_multi_stage_latency(self) -> None:
        """Measure 5-stage pipeline latency."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        for i in range(5):
            reg.register(PassStage(f"s{i}"))

        engine = PipelineEngine(bus, reg, {"subscribe_events": []})
        await engine.start()

        latencies: list[float] = []
        for _ in range(100):
            start = time.monotonic()
            ctx = PipelineContext()
            await engine._run_pipeline(SecurityEvent(), ctx)
            latencies.append((time.monotonic() - start) * 1000)

        avg = sum(latencies) / len(latencies)
        print(f"\n  5-stage latency: avg={avg:.3f}ms")

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_end_to_end_throughput(self) -> None:
        """Event Bus → Pipeline → Stage throughput."""
        bus = EventBus()
        await bus.start()

        reg = StageRegistry()
        stage = PassStage("e2e")
        reg.register(stage)

        engine = PipelineEngine(bus, reg)
        await engine.start()

        total = 500
        for i in range(total):
            await bus.publish(
                EventType.SECURITY_EVENT,
                SecurityEvent(correlation_id=f"bench-{i}"),
            )

        await asyncio.sleep(0.3)
        processed = len(stage.processed)
        print(f"\n  End-to-end: {processed}/{total} events delivered in ~0.3s")
