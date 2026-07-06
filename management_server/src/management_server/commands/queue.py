"""
Command queue — async priority queue for remote commands.

Four priority levels: IMMEDIATE, HIGH, NORMAL, LOW.
"""

from __future__ import annotations

import asyncio
from threading import Lock

import structlog

from management_server.commands.exceptions import QueueError
from management_server.commands.models import CommandPriority, RemoteCommand

logger = structlog.get_logger("commands.queue")

PRIORITY_ORDER = [
    CommandPriority.IMMEDIATE,
    CommandPriority.HIGH,
    CommandPriority.NORMAL,
    CommandPriority.LOW,
]


class CommandQueue:
    """Async priority queue for remote commands."""

    def __init__(self, max_size: int = 0) -> None:
        self._max_size = max_size
        self._queues: dict[str, asyncio.Queue[RemoteCommand]] = {
            p.value if hasattr(p, "value") else p: asyncio.Queue(maxsize=max_size)
            for p in PRIORITY_ORDER
        }
        self._lock = Lock()
        self._total_enqueued = 0
        self._total_dequeued = 0

    async def enqueue(self, command: RemoteCommand) -> None:
        """Enqueue a command at its priority level."""
        priority = command.priority.value
        if priority not in self._queues:
            raise QueueError(f"Invalid priority: '{priority}'")

        try:
            await self._queues[priority].put(command)
            with self._lock:
                self._total_enqueued += 1
        except asyncio.QueueFull:
            raise QueueError(f"Queue '{priority}' is full") from None

    def dequeue_nowait(self, priority: str = "normal") -> RemoteCommand | None:
        """Dequeue a command without blocking."""
        q = self._queues.get(priority)
        if q is None:
            return None
        try:
            cmd = q.get_nowait()
            with self._lock:
                self._total_dequeued += 1
            return cmd
        except asyncio.QueueEmpty:
            return None

    def depth(self, priority: str | None = None) -> int | dict[str, int]:
        """Get queue depth."""
        if priority is not None:
            q = self._queues.get(priority)
            return q.qsize() if q else 0
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
        d = self.depth()
        if isinstance(d, dict):
            return sum(d.values())
        return d
