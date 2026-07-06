"""
Command metrics — thread-safe counters for the Remote Command Framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class CommandMetricsSnapshot:
    commands_created: int = 0
    commands_authorized: int = 0
    commands_denied: int = 0
    commands_delivered: int = 0
    commands_acknowledged: int = 0
    commands_expired: int = 0
    commands_cancelled: int = 0
    authorization_failures: int = 0
    queue_depth: int = 0


class CommandMetricsCollector:
    """Thread-safe metrics collector for the Remote Command Framework."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._created = 0
        self._authorized = 0
        self._denied = 0
        self._delivered = 0
        self._acknowledged = 0
        self._expired = 0
        self._cancelled = 0
        self._auth_failures = 0

    def command_created(self) -> None:
        with self._lock:
            self._created += 1

    def command_authorized(self) -> None:
        with self._lock:
            self._authorized += 1

    def command_denied(self) -> None:
        with self._lock:
            self._denied += 1

    def command_delivered(self) -> None:
        with self._lock:
            self._delivered += 1

    def command_acknowledged(self) -> None:
        with self._lock:
            self._acknowledged += 1

    def command_expired(self) -> None:
        with self._lock:
            self._expired += 1

    def command_cancelled(self) -> None:
        with self._lock:
            self._cancelled += 1

    def authorization_failure(self) -> None:
        with self._lock:
            self._auth_failures += 1

    def snapshot(self, queue_depth: int = 0) -> CommandMetricsSnapshot:
        with self._lock:
            return CommandMetricsSnapshot(
                commands_created=self._created,
                commands_authorized=self._authorized,
                commands_denied=self._denied,
                commands_delivered=self._delivered,
                commands_acknowledged=self._acknowledged,
                commands_expired=self._expired,
                commands_cancelled=self._cancelled,
                authorization_failures=self._auth_failures,
                queue_depth=queue_depth,
            )
