"""
Comprehensive tests for the Event Bus and Event Model subsystems.

Coverage targets:
- Event creation and immutability
- Event validation
- Pub/sub operations
- Queue ordering (FIFO + priority)
- Subscriber isolation
- Graceful shutdown
- Correlation IDs
- Metrics
- Concurrent operations
- Performance (benchmark tests)
"""

from __future__ import annotations

import asyncio
import time

import pytest

from security_agent.event_bus import EventBus
from security_agent.events import (
    AlertEvent,
    BaseEvent,
    DeliveryStatus,
    EventBusShutdownError,
    EventCategory,
    EventEnvelope,
    EventType,
    HealthEvent,
    InternalEvent,
    InvalidEventError,
    LifecycleEvent,
    Priority,
    SecurityEvent,
)


class TestBaseEvent:
    def test_base_event_creation(self) -> None:
        event = BaseEvent(source="test")
        assert event.event_id is not None
        assert event.correlation_id is not None
        assert event.source == "test"
        assert event.severity == 0
        assert isinstance(event.event_id, str)

    def test_base_event_frozen(self) -> None:
        event = BaseEvent()
        with pytest.raises(AttributeError):
            event.source = "modified"  # type: ignore[misc]

    def test_severity_validation(self) -> None:
        with pytest.raises(ValueError, match="Severity must be 0-10"):
            BaseEvent(severity=11)
        with pytest.raises(ValueError, match="Severity must be 0-10"):
            BaseEvent(severity=-1)

    def test_severity_valid_range(self) -> None:
        for s in range(0, 11):
            assert BaseEvent(severity=s).severity == s

    def test_correlation_id_preserved(self) -> None:
        cid = "test-correlation-123"
        assert BaseEvent(correlation_id=cid).correlation_id == cid

    def test_correlation_id_auto_generated(self) -> None:
        assert BaseEvent().correlation_id != BaseEvent().correlation_id


class TestSpecificEvents:
    def test_security_event(self) -> None:
        event = SecurityEvent(
            source_ip="1.2.3.4",
            threat_score=85,
            confidence=90,
        )
        assert event.event_type == EventType.SECURITY_EVENT
        assert event.category == EventCategory.SECURITY
        assert event.priority == Priority.HIGH
        assert event.source_ip == "1.2.3.4"

    def test_health_event(self) -> None:
        event = HealthEvent(check_name="memory", status="warning")
        assert event.category == EventCategory.HEALTH

    def test_lifecycle_event(self) -> None:
        event = LifecycleEvent(transition="starting")
        assert event.category == EventCategory.LIFECYCLE
        assert event.priority == Priority.CRITICAL

    def test_alert_event(self) -> None:
        event = AlertEvent(title="SSH Brute Force", channel="critical")
        assert event.category == EventCategory.ALERT

    def test_internal_event(self) -> None:
        event = InternalEvent(internal_type="metrics")
        assert event.category == EventCategory.INTERNAL


class TestEventEnvelope:
    def test_envelope_creation(self) -> None:
        event = SecurityEvent(source_ip="1.2.3.4")
        envelope = EventEnvelope(event=event, publisher="test")
        assert envelope.event == event
        assert envelope.publisher == "test"
        assert envelope.delivery_status == DeliveryStatus.PENDING

    def test_envelope_frozen(self) -> None:
        envelope = EventEnvelope(event=BaseEvent())
        with pytest.raises(AttributeError):
            envelope.publisher = "modified"  # type: ignore[misc]


class TestEventBusLifecycle:
    @pytest.mark.asyncio
    async def test_start_and_shutdown(self) -> None:
        bus = EventBus()
        assert not bus.is_started
        await bus.start()
        assert bus.is_started
        await bus.shutdown()
        assert bus.is_shutting_down

    @pytest.mark.asyncio
    async def test_double_shutdown_safe(self) -> None:
        bus = EventBus()
        await bus.start()
        await bus.shutdown()
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_publish_after_shutdown_raises(self) -> None:
        bus = EventBus()
        await bus.start()
        await bus.shutdown()
        with pytest.raises(EventBusShutdownError):
            await bus.publish(EventType.HEALTH_CHECK, BaseEvent())


class TestPublishSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_and_receive(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[EventEnvelope] = []

        async def handler(envelope: EventEnvelope) -> None:
            received.append(envelope)

        bus.subscribe(EventType.SECURITY_EVENT, handler, name="handler1")
        await bus.publish(EventType.SECURITY_EVENT, SecurityEvent())
        await asyncio.sleep(0.05)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        bus = EventBus()
        await bus.start()
        r1: list[EventEnvelope] = []
        r2: list[EventEnvelope] = []

        async def h1(e: EventEnvelope) -> None:
            r1.append(e)

        async def h2(e: EventEnvelope) -> None:
            r2.append(e)

        bus.subscribe(EventType.SECURITY_EVENT, h1, name="h1")
        bus.subscribe(EventType.SECURITY_EVENT, h2, name="h2")
        await bus.publish(EventType.SECURITY_EVENT, SecurityEvent())
        await asyncio.sleep(0.05)
        assert len(r1) == 1
        assert len(r2) == 1

    @pytest.mark.asyncio
    async def test_subscriber_isolation(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[EventEnvelope] = []

        async def failing(e: EventEnvelope) -> None:
            raise ValueError(f"Fail for {e.event.event_id}")

        async def good(e: EventEnvelope) -> None:
            received.append(e)

        bus.subscribe(EventType.SECURITY_EVENT, failing, name="fail")
        bus.subscribe(EventType.SECURITY_EVENT, good, name="good")
        await bus.publish(EventType.SECURITY_EVENT, SecurityEvent())
        await asyncio.sleep(0.05)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[EventEnvelope] = []

        async def handler(e: EventEnvelope) -> None:
            received.append(e)

        sub = bus.subscribe(EventType.SECURITY_EVENT, handler, name="test")
        await bus.publish(EventType.SECURITY_EVENT, SecurityEvent())
        await asyncio.sleep(0.05)
        assert len(received) == 1

        bus.unsubscribe(sub)
        await bus.publish(EventType.SECURITY_EVENT, SecurityEvent())
        await asyncio.sleep(0.05)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_publish_many(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[EventEnvelope] = []

        async def handler(e: EventEnvelope) -> None:
            received.append(e)

        bus.subscribe(EventType.SECURITY_EVENT, handler, name="test")
        events = [
            (EventType.SECURITY_EVENT, SecurityEvent(source_ip=f"1.2.3.{i}"))
            for i in range(10)
        ]
        await bus.publish_many(events)
        await asyncio.sleep(0.05)
        assert len(received) == 10

    @pytest.mark.asyncio
    async def test_subscribe_after_start(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[EventEnvelope] = []

        async def handler(e: EventEnvelope) -> None:
            received.append(e)

        bus.subscribe(EventType.SECURITY_EVENT, handler, name="test")
        await bus.publish(EventType.SECURITY_EVENT, SecurityEvent())
        await asyncio.sleep(0.05)
        assert len(received) == 1


class TestQueueOrdering:
    @pytest.mark.asyncio
    async def test_fifo_within_priority(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[str] = []

        async def handler(e: EventEnvelope) -> None:
            received.append(e.event.metadata.get("seq", ""))

        bus.subscribe(EventType.INTERNAL_METRICS, handler, name="test")
        for i in range(5):
            await bus.publish(
                EventType.INTERNAL_METRICS,
                InternalEvent(priority=Priority.NORMAL, metadata={"seq": str(i)}),
            )
        await asyncio.sleep(0.05)
        assert received == ["0", "1", "2", "3", "4"]

    @pytest.mark.asyncio
    async def test_priority_ordering(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[int] = []

        async def handler(e: EventEnvelope) -> None:
            received.append(e.event.priority)

        bus.subscribe(EventType.INTERNAL_METRICS, handler, name="test")
        for prio in [
            Priority.BACKGROUND,
            Priority.LOW,
            Priority.NORMAL,
            Priority.HIGH,
            Priority.CRITICAL,
        ]:
            await bus.publish(EventType.INTERNAL_METRICS, InternalEvent(priority=prio))
        await asyncio.sleep(0.05)
        assert received == [
            Priority.CRITICAL,
            Priority.HIGH,
            Priority.NORMAL,
            Priority.LOW,
            Priority.BACKGROUND,
        ]


class TestCorrelationId:
    @pytest.mark.asyncio
    async def test_correlation_id_preserved(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[EventEnvelope] = []

        async def handler(e: EventEnvelope) -> None:
            received.append(e)

        bus.subscribe(EventType.SECURITY_EVENT, handler, name="test")
        await bus.publish(
            EventType.SECURITY_EVENT, SecurityEvent(correlation_id="chain-001")
        )
        await asyncio.sleep(0.05)
        assert received[0].event.correlation_id == "chain-001"


class TestEventValidation:
    @pytest.mark.asyncio
    async def test_invalid_event_type_raises(self) -> None:
        bus = EventBus()
        await bus.start()
        with pytest.raises(InvalidEventError):
            await bus.publish(EventType.SECURITY_EVENT, "not_an_event")  # type: ignore[arg-type]


class TestMetrics:
    @pytest.mark.asyncio
    async def test_metrics_snapshot(self) -> None:
        bus = EventBus()
        await bus.start()
        snapshot = bus.metrics_snapshot()
        assert isinstance(snapshot.total_published, int)

    @pytest.mark.asyncio
    async def test_metrics_after_publish(self) -> None:
        bus = EventBus()
        await bus.start()

        async def handler(e: EventEnvelope) -> None:
            pass

        bus.subscribe(EventType.SECURITY_EVENT, handler, name="test")
        await bus.publish(EventType.SECURITY_EVENT, SecurityEvent())
        await asyncio.sleep(0.05)
        snapshot = bus.metrics_snapshot()
        assert snapshot.total_published >= 1
        assert snapshot.subscriber_count >= 1

    @pytest.mark.asyncio
    async def test_metrics_subscriber_failure(self) -> None:
        bus = EventBus()
        await bus.start()

        async def fail_handler(e: EventEnvelope) -> None:
            raise ValueError(f"Fail for {e.event.event_id}")

        bus.subscribe(EventType.SECURITY_EVENT, fail_handler, name="fail")
        await bus.publish(EventType.SECURITY_EVENT, SecurityEvent())
        await asyncio.sleep(0.05)
        snapshot = bus.metrics_snapshot()
        assert snapshot.total_failed >= 1


class TestQueue:
    @pytest.mark.asyncio
    async def test_queue_empty_after_drain(self) -> None:
        from security_agent.event_bus.queue import PriorityQueue

        q = PriorityQueue()
        assert await q.is_empty
        await q.put(EventEnvelope(event=BaseEvent()))
        drained = await q.drain()
        assert len(drained) == 1
        assert await q.is_empty

    @pytest.mark.asyncio
    async def test_queue_overflow(self) -> None:
        from security_agent.event_bus.queue import PriorityQueue
        from security_agent.events.exceptions import QueueFullError

        q = PriorityQueue(maxsize=2)
        await q.put_nowait(EventEnvelope(event=BaseEvent()))
        await q.put_nowait(EventEnvelope(event=BaseEvent()))
        with pytest.raises(QueueFullError):
            await q.put_nowait(EventEnvelope(event=BaseEvent()))

    @pytest.mark.asyncio
    async def test_queue_clear(self) -> None:
        from security_agent.event_bus.queue import PriorityQueue

        q = PriorityQueue()
        await q.put(EventEnvelope(event=BaseEvent()))
        await q.put(EventEnvelope(event=BaseEvent()))
        count = await q.clear()
        assert count == 2
        assert await q.is_empty


class TestPublisher:
    @pytest.mark.asyncio
    async def test_publisher_scoped(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[EventEnvelope] = []

        async def handler(e: EventEnvelope) -> None:
            received.append(e)

        bus.subscribe(EventType.SECURITY_EVENT, handler, name="test")
        pub = bus.create_publisher("test-component")
        assert pub.name == "test-component"

        await pub.publish(EventType.SECURITY_EVENT, SecurityEvent())
        await asyncio.sleep(0.05)
        assert len(received) == 1


class TestConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_publishers(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[EventEnvelope] = []

        async def handler(e: EventEnvelope) -> None:
            received.append(e)

        bus.subscribe(EventType.SECURITY_EVENT, handler, name="test")

        async def publish_task(n: int) -> None:
            for i in range(20):
                await bus.publish(
                    EventType.SECURITY_EVENT,
                    SecurityEvent(metadata={"seq": f"{n}-{i}"}),
                )

        tasks = [asyncio.create_task(publish_task(n)) for n in range(5)]
        await asyncio.gather(*tasks)
        await asyncio.sleep(0.1)
        assert len(received) == 100

    @pytest.mark.asyncio
    async def test_high_volume(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[EventEnvelope] = []

        async def handler(e: EventEnvelope) -> None:
            received.append(e)

        bus.subscribe(EventType.SECURITY_EVENT, handler, name="test")
        for i in range(1000):
            await bus.publish(
                EventType.SECURITY_EVENT,
                SecurityEvent(metadata={"seq": i}),
            )
        await asyncio.sleep(0.2)
        assert len(received) == 1000

    @pytest.mark.asyncio
    async def test_slow_subscriber(self) -> None:
        bus = EventBus()
        await bus.start()

        async def slow(_e: EventEnvelope) -> None:
            await asyncio.sleep(0.001)

        bus.subscribe(EventType.SECURITY_EVENT, slow, name="slow")
        await bus.publish(EventType.SECURITY_EVENT, SecurityEvent())
        await asyncio.sleep(0.05)
        assert not bus.is_shutting_down


class TestBenchmarks:
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_publish_latency(self) -> None:
        bus = EventBus()
        await bus.start()

        async def handler(e: EventEnvelope) -> None:
            pass

        bus.subscribe(EventType.SECURITY_EVENT, handler, name="bench")
        latencies: list[float] = []
        for _ in range(100):
            start = time.monotonic()
            await bus.publish(EventType.SECURITY_EVENT, SecurityEvent())
            latencies.append((time.monotonic() - start) * 1000)

        avg = sum(latencies) / len(latencies)
        max_lat = max(latencies)
        print(f"\n  Publish latency: avg={avg:.3f}ms, max={max_lat:.3f}ms")
        assert avg < 10.0

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_throughput(self) -> None:
        bus = EventBus()
        await bus.start()
        count = 0

        async def handler(_e: EventEnvelope) -> None:
            nonlocal count
            count += 1

        bus.subscribe(EventType.SECURITY_EVENT, handler, name="bench")
        total = 5000
        start = time.monotonic()
        for i in range(total):
            await bus.publish(
                EventType.SECURITY_EVENT,
                SecurityEvent(metadata={"seq": i}),
            )
        elapsed = 0.0
        while count < total and elapsed < 5.0:
            await asyncio.sleep(0.05)
            elapsed = time.monotonic() - start

        total_time = time.monotonic() - start
        throughput = count / total_time if total_time > 0 else 0
        print(
            f"\n  Throughput: {throughput:.0f} events/sec ({count} in {total_time:.2f}s)"
        )
        assert count == total

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_memory_usage(self) -> None:
        import tracemalloc

        tracemalloc.start()
        bus = EventBus()
        await bus.start()
        acc: list[EventEnvelope] = []

        async def handler(e: EventEnvelope) -> None:
            acc.append(e)

        bus.subscribe(EventType.SECURITY_EVENT, handler, name="bench")
        for i in range(1000):
            await bus.publish(
                EventType.SECURITY_EVENT,
                SecurityEvent(metadata={"seq": i}),
            )
        await asyncio.sleep(0.2)
        _, peak = tracemalloc.get_traced_memory()
        await bus.shutdown()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024
        print(f"\n  Peak memory (1000 events): {peak_mb:.2f} MB")
        assert peak_mb < 50
