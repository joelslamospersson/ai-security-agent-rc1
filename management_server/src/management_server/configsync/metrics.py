"""
Config sync metrics — thread-safe counters.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class ConfigSyncMetricsSnapshot:
    packages_created: int = 0
    packages_published: int = 0
    packages_downloaded: int = 0
    package_failures: int = 0
    synchronization_requests: int = 0
    version_mismatches: int = 0


class ConfigSyncMetricsCollector:
    """Thread-safe metrics collector for the Config Sync Framework."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._created = 0
        self._published = 0
        self._downloaded = 0
        self._failures = 0
        self._sync_requests = 0
        self._mismatches = 0

    def package_created(self) -> None:
        with self._lock:
            self._created += 1

    def package_published(self) -> None:
        with self._lock:
            self._published += 1

    def package_downloaded(self) -> None:
        with self._lock:
            self._downloaded += 1

    def package_failure(self) -> None:
        with self._lock:
            self._failures += 1

    def sync_requested(self) -> None:
        with self._lock:
            self._sync_requests += 1

    def version_mismatch(self) -> None:
        with self._lock:
            self._mismatches += 1

    def snapshot(self) -> ConfigSyncMetricsSnapshot:
        with self._lock:
            return ConfigSyncMetricsSnapshot(
                packages_created=self._created,
                packages_published=self._published,
                packages_downloaded=self._downloaded,
                package_failures=self._failures,
                synchronization_requests=self._sync_requests,
                version_mismatches=self._mismatches,
            )
