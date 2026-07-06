"""
Discord Adapter metrics — thread-safe counters.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class DiscordBotMetricsSnapshot:
    guilds_connected: int = 0
    channels_created: int = 0
    permission_repairs: int = 0
    notifications_rendered: int = 0
    threads_created: int = 0
    status_updates: int = 0
    api_latency_ms: float = 0.0


class DiscordBotMetricsCollector:
    """Thread-safe metrics collector for the Discord Adapter."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._guilds = 0
        self._channels_created = 0
        self._permission_repairs = 0
        self._notifications_rendered = 0
        self._threads_created = 0
        self._status_updates = 0
        self._api_latencies: list[float] = []

    def guild_connected(self) -> None:
        with self._lock:
            self._guilds += 1

    def channel_created(self) -> None:
        with self._lock:
            self._channels_created += 1

    def permission_repair(self) -> None:
        with self._lock:
            self._permission_repairs += 1

    def notification_rendered(self) -> None:
        with self._lock:
            self._notifications_rendered += 1

    def thread_created(self) -> None:
        with self._lock:
            self._threads_created += 1

    def status_updated(self) -> None:
        with self._lock:
            self._status_updates += 1

    def api_latency(self, latency_ms: float) -> None:
        with self._lock:
            self._api_latencies.append(latency_ms)

    def set_guild_count(self, count: int) -> None:
        with self._lock:
            self._guilds = count

    def snapshot(self) -> DiscordBotMetricsSnapshot:
        with self._lock:
            avg_latency = 0.0
            if self._api_latencies:
                avg_latency = sum(self._api_latencies) / len(self._api_latencies)
            return DiscordBotMetricsSnapshot(
                guilds_connected=self._guilds,
                channels_created=self._channels_created,
                permission_repairs=self._permission_repairs,
                notifications_rendered=self._notifications_rendered,
                threads_created=self._threads_created,
                status_updates=self._status_updates,
                api_latency_ms=round(avg_latency, 2),
            )
