"""
Discord metrics — thread-safe counters for the Discord Registration Framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class DiscordMetricsSnapshot:
    guilds_registered: int = 0
    guilds_verified: int = 0
    guilds_deleted: int = 0
    machines_associated: int = 0
    validation_failures: int = 0
    config_requests: int = 0


class DiscordMetricsCollector:
    """Thread-safe metrics collector for the Discord Registration Framework."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._registered = 0
        self._verified = 0
        self._deleted = 0
        self._machines = 0
        self._validation_failures = 0
        self._config_requests = 0

    def guild_registered(self) -> None:
        with self._lock:
            self._registered += 1

    def guild_verified(self) -> None:
        with self._lock:
            self._verified += 1

    def guild_deleted(self) -> None:
        with self._lock:
            self._deleted += 1

    def machine_associated(self) -> None:
        with self._lock:
            self._machines += 1

    def validation_failure(self) -> None:
        with self._lock:
            self._validation_failures += 1

    def config_requested(self) -> None:
        with self._lock:
            self._config_requests += 1

    def snapshot(self) -> DiscordMetricsSnapshot:
        with self._lock:
            return DiscordMetricsSnapshot(
                guilds_registered=self._registered,
                guilds_verified=self._verified,
                guilds_deleted=self._deleted,
                machines_associated=self._machines,
                validation_failures=self._validation_failures,
                config_requests=self._config_requests,
            )
