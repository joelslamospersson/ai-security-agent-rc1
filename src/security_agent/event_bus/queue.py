"""
Priority-aware async queue for the Event Bus.

Preserves FIFO ordering within the same priority level.
Higher priority events are dequeued before lower priority ones.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field

from security_agent.events.envelope import EventEnvelope
from security_agent.events.exceptions import (
    PriorityQueueError,
    QueueEmptyError,
    QueueFullError,
)
from security_agent.events.priority import Priority


@dataclass(order=True, slots=True)
class QueueEntry:
    """Internal queue entry used for priority ordering.

    Comparison is by (priority, sequence). Lower priority value = higher priority.
    Sequence preserves FIFO within the same priority.
    """

    priority: int  # Priority enum value (lower = higher priority)
    sequence: int  # Monotonically increasing sequence number
    envelope: EventEnvelope = field(compare=False)


class PriorityQueue:
    """Priority queue for Event Bus messages.

    Maintains separate FIFO deques per priority level.
    This avoids O(log n) heap operations on every enqueue/dequeue.

    Queue ordering:
    1. Events are grouped by priority level.
    2. Within the same priority, events are processed FIFO.
    3. Higher priority queues are drained before lower ones.
    """

    def __init__(self, maxsize: int = 0, name: str = "default") -> None:
        self._name = name
        self._maxsize = maxsize
        self._queues: dict[int, deque[EventEnvelope]] = {
            Priority.CRITICAL: deque(),
            Priority.HIGH: deque(),
            Priority.NORMAL: deque(),
            Priority.LOW: deque(),
            Priority.BACKGROUND: deque(),
        }
        self._total = 0
        self._sequence = 0
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)

    @property
    def name(self) -> str:
        return self._name

    @property
    def maxsize(self) -> int:
        return self._maxsize

    @property
    async def qsize(self) -> int:
        async with self._lock:
            return self._total

    @property
    async def is_empty(self) -> bool:
        async with self._lock:
            return self._total == 0

    @property
    async def is_full(self) -> bool:
        if self._maxsize <= 0:
            return False
        async with self._lock:
            return self._total >= self._maxsize

    async def put(self, envelope: EventEnvelope) -> None:
        """Enqueue an event. Blocks if the queue is full (backpressure)."""
        while True:
            async with self._lock:
                if self._maxsize <= 0 or self._total < self._maxsize:
                    priority = envelope.event.priority

                    if priority not in self._queues:
                        raise PriorityQueueError(f"Unknown priority level: {priority}")

                    self._queues[priority].append(envelope)
                    self._total += 1
                    self._not_empty.notify()
                    return

            # Queue is full — wait briefly and retry (backpressure)
            await asyncio.sleep(0.001)

    async def put_nowait(self, envelope: EventEnvelope) -> None:
        """Enqueue an event without blocking.

        Raises QueueFullError if the queue is at capacity.
        """
        async with self._lock:
            if self._maxsize > 0 and self._total >= self._maxsize:
                raise QueueFullError(
                    f"Queue '{self._name}' is full ({self._total}/{self._maxsize})"
                )

            priority = envelope.event.priority
            if priority not in self._queues:
                raise PriorityQueueError(f"Unknown priority level: {priority}")

            self._queues[priority].append(envelope)
            self._total += 1
            self._not_empty.notify()

    async def get(self) -> EventEnvelope:
        """Dequeue the highest-priority event.

        Blocks until an event is available.
        """
        async with self._lock:
            while self._total == 0:
                await self._not_empty.wait()

            return self._dequeue_highest_priority()

    async def get_nowait(self) -> EventEnvelope:
        """Dequeue without blocking.

        Raises QueueEmptyError if no events are available.
        """
        async with self._lock:
            if self._total == 0:
                raise QueueEmptyError(f"Queue '{self._name}' is empty")
            return self._dequeue_highest_priority()

    def _dequeue_highest_priority(self) -> EventEnvelope:
        """Dequeue from the highest non-empty priority level."""
        for priority in sorted(self._queues.keys()):
            q = self._queues[priority]
            if q:
                envelope = q.popleft()
                self._total -= 1
                return envelope

        raise QueueEmptyError(f"Queue '{self._name}' has no events (race)")

    async def drain(self) -> list[EventEnvelope]:
        """Dequeue all remaining events.

        Used during shutdown to process leftover events.
        """
        result: list[EventEnvelope] = []
        async with self._lock:
            for priority in sorted(self._queues.keys()):
                q = self._queues[priority]
                while q:
                    result.append(q.popleft())
                    self._total -= 1
        return result

    async def clear(self) -> int:
        """Clear all events from the queue. Returns count of cleared events."""
        count = 0
        async with self._lock:
            for q in self._queues.values():
                count += len(q)
                q.clear()
            self._total = 0
        return count
