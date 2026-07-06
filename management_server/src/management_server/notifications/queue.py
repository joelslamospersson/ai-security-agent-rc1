"""
Notification queue — asynchronous priority queue system.

Five priority levels: IMMEDIATE, HIGH, NORMAL, LOW, BULK.
Each priority has its own asyncio.Queue for independent processing.
"""

from __future__ import annotations

import asyncio
from threading import Lock

import structlog

from management_server.notifications.exceptions import QueueError
from management_server.notifications.models import Notification, QueueItem, RetryPolicy

logger = structlog.get_logger("notifications.queue")

PRIORITY_LEVELS = ["immediate", "high", "normal", "low", "bulk"]


class NotificationQueue:
    """Async priority queue system for notifications.

    Each priority level has its own asyncio.Queue.
    Supports enqueue, dequeue, and depth queries.
    """

    def __init__(self, max_size: int = 0) -> None:
        self._max_size = max_size
        self._queues: dict[str, asyncio.Queue[QueueItem]] = {
            priority: asyncio.Queue(maxsize=max_size) for priority in PRIORITY_LEVELS
        }
        self._lock = Lock()
        self._total_enqueued = 0
        self._total_dequeued = 0

    async def enqueue(
        self,
        notification: Notification,
        priority: str = "normal",
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        """Enqueue a notification."""
        if priority not in self._queues:
            raise QueueError(f"Invalid priority queue: '{priority}'")

        item = QueueItem(
            notification=notification,
            priority=priority,
            retry_policy=retry_policy or RetryPolicy(),
        )

        try:
            await self._queues[priority].put(item)
            with self._lock:
                self._total_enqueued += 1
        except asyncio.QueueFull:
            raise QueueError(f"Queue '{priority}' is full") from None

    def dequeue_nowait(self, priority: str = "normal") -> QueueItem | None:
        """Dequeue an item without blocking."""
        if priority not in self._queues:
            return None
        try:
            item = self._queues[priority].get_nowait()
            with self._lock:
                self._total_dequeued += 1
            return item
        except asyncio.QueueEmpty:
            return None

    async def dequeue(self, priority: str = "normal") -> QueueItem:
        """Dequeue an item, blocking if necessary."""
        if priority not in self._queues:
            raise QueueError(f"Invalid priority queue: '{priority}'")
        item = await self._queues[priority].get()
        with self._lock:
            self._total_dequeued += 1
        return item

    def depth(self, priority: str | None = None) -> int | dict[str, int]:
        """Get queue depth.

        If priority is None, returns a dict of all depths.
        """
        if priority is not None:
            if priority not in self._queues:
                return 0
            return self._queues[priority].qsize()

        return {p: q.qsize() for p, q in self._queues.items()}

    @property
    def total_enqueued(self) -> int:
        with self._lock:
            return self._total_enqueued

    @property
    def total_dequeued(self) -> int:
        with self._lock:
            return self._total_dequeued

    @property
    def total_pending(self) -> int:
        depths = self.depth()
        if isinstance(depths, dict):
            return sum(depths.values())
        return depths
