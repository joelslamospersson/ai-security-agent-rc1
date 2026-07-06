"""
Background Worker Supervisor — monitors, detects, and restarts workers.

Detects crashed, hung, deadlocked workers.
Attempts automatic restart when appropriate.
Escalates after repeated failures.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import structlog

from management_server.health.models import WorkerInfo, WorkerStatus

logger = structlog.get_logger("health.worker_supervisor")

HUNG_TIMEOUT_SECONDS = 120  # Worker considered hung if no heartbeat for 2 minutes
MAX_RESTART_THRESHOLD = 5  # Max restarts before escalation


class WorkerSupervisor:
    """Supervises background workers/tasks.

    Provides heartbeat-based monitoring with automatic restart and escalation.
    """

    def __init__(self) -> None:
        self._workers: dict[str, WorkerInfo] = {}
        self._restart_handlers: dict[str, Callable[[], Any]] = {}
        self._escalation_callbacks: list[Callable[[str, str], Any]] = []

    def register(
        self,
        name: str,
        restart_handler: Callable[[], Any] | None = None,
        max_restarts: int = 3,
    ) -> None:
        """Register a worker for supervision."""
        self._workers[name] = WorkerInfo(
            name=name,
            status=WorkerStatus.RUNNING,
            max_restarts=max_restarts,
        )
        if restart_handler:
            self._restart_handlers[name] = restart_handler

    def heartbeat(self, name: str) -> None:
        """Record a worker heartbeat."""
        if name in self._workers:
            self._workers[name].last_heartbeat = datetime.now(tz=UTC)
            self._workers[name].status = WorkerStatus.RUNNING

    def mark_crashed(self, name: str, error: str = "") -> None:
        """Mark a worker as crashed."""
        if name in self._workers:
            self._workers[name].status = WorkerStatus.CRASHED
            self._workers[name].error = error
            logger.error("Worker crashed", worker=name, error=error)

    def mark_hung(self, name: str) -> None:
        """Mark a worker as hung."""
        if name in self._workers:
            self._workers[name].status = WorkerStatus.HUNG
            logger.warning("Worker hung", worker=name)

    def on_escalation(self, callback: Callable[[str, str], Any]) -> None:
        """Register an escalation callback (for alerts/audit)."""
        self._escalation_callbacks.append(callback)

    async def check_all(self) -> list[str]:
        """Check all workers. Returns list of restarted workers."""
        now = datetime.now(tz=UTC)
        restarted: list[str] = []

        for name, info in list(self._workers.items()):
            # Check for hung workers
            if info.status == WorkerStatus.RUNNING:
                elapsed = (now - info.last_heartbeat).total_seconds()
                if elapsed > HUNG_TIMEOUT_SECONDS:
                    self.mark_hung(name)

            # Restart crashed/hung workers
            if info.status in (WorkerStatus.CRASHED, WorkerStatus.HUNG, WorkerStatus.DEADLOCKED):
                if info.restart_count < info.max_restarts and name in self._restart_handlers:
                    try:
                        handler = self._restart_handlers[name]
                        if callable(handler):
                            result = handler()
                            if hasattr(result, "__await__"):
                                await result
                        info.restart_count += 1
                        info.status = WorkerStatus.RUNNING
                        info.last_heartbeat = now
                        info.error = ""
                        restarted.append(name)
                        logger.info("Worker restarted", worker=name, attempt=info.restart_count)
                    except Exception as e:
                        logger.error("Worker restart failed", worker=name, error=str(e))
                        info.restart_count += 1

                # Escalate if max restarts exceeded
                if info.restart_count >= info.max_restarts:
                    for callback in self._escalation_callbacks:
                        try:
                            cb_result = callback(name, info.error or "Max restarts exceeded")
                            if hasattr(cb_result, "__await__"):
                                await cb_result
                        except Exception:
                            pass

        return restarted

    def get_workers(self) -> dict[str, WorkerInfo]:
        return dict(self._workers)
