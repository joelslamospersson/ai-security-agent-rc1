"""
Event Bus — asynchronous publish/subscribe backbone for the application.

Every subsystem communicates exclusively through the Event Bus.
No module ever calls another module's methods directly.

Key guarantees:
- One failing subscriber never affects others
- Events are delivered in priority order
- Correlation IDs are preserved across event chains
- Graceful shutdown drains all queues
- Backpressure prevents OOM
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from security_agent.event_bus.metrics import BusMetricsCollector, BusMetricsSnapshot
from security_agent.event_bus.publisher import Publisher
from security_agent.event_bus.queue import PriorityQueue
from security_agent.event_bus.subscriber import (
    SLOW_SUBSCRIBER_THRESHOLD,
    EventHandler,
    SubscriberRegistry,
    Subscription,
)
from security_agent.events.envelope import EventEnvelope
from security_agent.events.event_types import EventType
from security_agent.events.exceptions import (
    EventBusShutdownError,
    InvalidEventError,
    QueueFullError,
)
from security_agent.events.models import BaseEvent

logger = logging.getLogger("eventbus")

# Default queue size per event type
_DEFAULT_QUEUE_SIZE = 10000


class EventBus:
    """Asynchronous publish/subscribe Event Bus.

    Usage:
        bus = EventBus()
        await bus.start()

        # Subscribe
        sub = bus.subscribe(EventType.SECURITY_EVENT, my_handler)

        # Publish
        event = SecurityEvent(source_ip="1.2.3.4")
        await bus.publish(EventType.SECURITY_EVENT, event)

        # Shutdown
        await bus.shutdown()

    Concurrency:
        All public methods are safe to call from any asyncio task.
        Internal dispatch uses per-event-type worker tasks.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._subscribers = SubscriberRegistry()
        self._queues: dict[EventType, PriorityQueue] = {}
        self._workers: dict[EventType, asyncio.Task[None]] = {}
        self._metrics = BusMetricsCollector()
        self._shutting_down = False
        self._started = False
        self._queue_size = self._config.get("event_bus_queue_size", _DEFAULT_QUEUE_SIZE)

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> None:
        """Start the Event Bus.

        Must be called before any publish/subscribe operations.
        """
        self._started = True
        logger.info("EventBus started", extra={"queue_size": self._queue_size})

    async def shutdown(self) -> None:
        """Graceful shutdown.

        Flow:
        1. Stop accepting new events (shutting_down = True)
        2. Drain all queues
        3. Cancel worker tasks
        4. Log final metrics
        """
        if self._shutting_down:
            return
        self._shutting_down = True
        logger.info("EventBus shutting down")

        total_drained = 0
        # Drain all queues
        for _event_type, queue in self._queues.items():
            drained = await queue.drain()
            total_drained += len(drained)
            # Process drained events
            for envelope in drained:
                await self._deliver(envelope)

        for _event_type, task in self._workers.items():
            task.cancel()

        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers.values(), return_exceptions=True)

        self._workers.clear()
        self._queues.clear()

        logger.info(
            "EventBus shutdown complete",
            extra={
                "events_drained": total_drained,
                "total_published": self._metrics.snapshot().total_published,
            },
        )

    # =========================================================================
    # Subscribe / Unsubscribe
    # =========================================================================

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
        name: str = "",
    ) -> Subscription:
        """Register a subscriber for an event type.

        The handler will be called for every event of this type.
        Handlers are async functions: async def handler(envelope).

        Returns a Subscription token for unsubscription.
        """
        sub = self._subscribers.subscribe(event_type, handler, name=name)

        # Create queue + worker for this event type if not exists
        if event_type not in self._queues:
            self._queues[event_type] = PriorityQueue(
                maxsize=self._queue_size,
                name=f"queue-{event_type.name}",
            )

        if event_type not in self._workers and self._started:
            self._workers[event_type] = asyncio.create_task(
                self._dispatch_loop(event_type)
            )

        logger.debug(
            "Subscriber registered",
            extra={
                "event_type": event_type.name,
                "subscriber": name,
                "total": self._subscribers.subscription_count,
            },
        )
        return sub

    def unsubscribe(self, subscription: Subscription) -> bool:
        """Remove a subscriber registration."""
        result = self._subscribers.unsubscribe(subscription)
        if result:
            logger.debug(
                "Subscriber unregistered",
                extra={
                    "event_type": subscription.event_type.name,
                    "subscriber": subscription.name,
                },
            )
        return bool(result)

    def subscriber_count(self) -> int:
        """Return total number of active subscriptions."""
        return int(self._subscribers.subscription_count)

    # =========================================================================
    # Publish
    # =========================================================================

    async def publish(
        self,
        event_type: EventType,
        event: BaseEvent,
        publisher: str = "",
    ) -> None:
        """Publish an event to all subscribers.

        The event is wrapped in an EventEnvelope and queued for delivery.
        Raises EventBusShutdownError if the bus is shutting down.
        Raises InvalidEventError if the event type is invalid.
        """
        if self._shutting_down:
            raise EventBusShutdownError("EventBus is shutting down")

        if not isinstance(event, BaseEvent):
            raise InvalidEventError(
                f"Expected BaseEvent instance, got {type(event).__name__}"
            )

        publish_start = time.monotonic()

        # Create envelope
        envelope = EventEnvelope(
            event=event,
            publisher=publisher,
            queue_name=f"queue-{event_type.name}",
        )

        # Route to queue
        queue = self._queues.get(event_type)
        if queue is None:
            # No subscribers — drop silently
            self._metrics.increment_dropped()
            return

        try:
            await queue.put(envelope)
            self._metrics.increment_published()
            depth = await queue.qsize
            self._metrics.update_peak_depth(depth)
        except QueueFullError:
            self._metrics.increment_dropped()
            logger.warning(
                "Queue full, event dropped",
                extra={
                    "event_type": event_type.name,
                    "queue": queue.name,
                    "event_id": event.event_id,
                },
            )
            return

        latency = time.monotonic() - publish_start
        self._metrics.record_publish_latency(latency)

    async def publish_many(
        self,
        events: list[tuple[EventType, BaseEvent]],
        publisher: str = "",
    ) -> None:
        """Publish multiple events efficiently."""
        for event_type, event in events:
            await self.publish(event_type, event, publisher=publisher)

    # =========================================================================
    # Internal Dispatch
    # =========================================================================

    async def _dispatch_loop(self, event_type: EventType) -> None:
        """Background worker: dequeue and deliver events for one event type."""
        queue = self._queues.get(event_type)
        if queue is None:
            return

        logger.debug(
            "Dispatch worker started",
            extra={"event_type": event_type.name},
        )

        try:
            while not self._shutting_down:
                try:
                    envelope = await queue.get()
                except asyncio.CancelledError:
                    break

                await self._deliver(envelope)

        except asyncio.CancelledError:
            pass
        finally:
            logger.debug(
                "Dispatch worker stopped",
                extra={"event_type": event_type.name},
            )

    async def _deliver(self, envelope: EventEnvelope) -> None:
        """Deliver an envelope to all subscribers for its event type.

        One failing subscriber never affects others.
        Exceptions are caught, logged, and metrified.
        """
        event_type = envelope.event.event_type
        subs = self._subscribers.get_handlers(event_type)

        if not subs:
            self._metrics.increment_dropped()
            return

        start = time.monotonic()
        for sub in subs:
            if sub.handler is None:
                continue

            handler_start = time.monotonic()
            try:
                await sub.handler(envelope)
                self._metrics.increment_delivered()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._metrics.increment_failed()
                logger.error(
                    "Subscriber delivery failed",
                    extra={
                        "subscriber": sub.name,
                        "event_type": event_type.name,
                        "event_id": envelope.event.event_id,
                        "error": str(e),
                    },
                    exc_info=True,
                )

            handler_latency = time.monotonic() - handler_start
            if handler_latency > SLOW_SUBSCRIBER_THRESHOLD:
                self._metrics.increment_slow_subscriber()
                logger.warning(
                    "Slow subscriber detected",
                    extra={
                        "subscriber": sub.name,
                        "event_type": event_type.name,
                        "latency_ms": round(handler_latency * 1000),
                    },
                )

        delivery_latency = time.monotonic() - start
        self._metrics.record_delivery_latency(delivery_latency)

    # =========================================================================
    # Metrics
    # =========================================================================

    def metrics_snapshot(self) -> BusMetricsSnapshot:
        """Return current bus metrics snapshot."""
        total_depth = 0
        queue_names: list[str] = []
        for _event_type, q in self._queues.items():
            queue_names.append(q.name)
            total_depth += (
                q._total
            )  # approximate (behind lock but good enough for metrics)

        return self._metrics.snapshot(
            current_depth=total_depth,
            queue_capacity=self._queue_size,
            subscriber_count=self._subscribers.subscription_count,
            queue_names=queue_names,
        )

    # =========================================================================
    # Publisher factory
    # =========================================================================

    def create_publisher(self, component_name: str) -> Publisher:
        """Create a Publisher scoped to a specific component."""
        return Publisher(self.publish, component_name)

    # =========================================================================
    # Query
    # =========================================================================

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    @property
    def is_started(self) -> bool:
        return self._started
