"""
Logging metrics — thread-safe counters.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class LoggingMetricsSnapshot:
    log_entries_written: int = 0
    reports_generated: int = 0
    bytes_written: int = 0
    bytes_compressed: int = 0
    files_rotated: int = 0
    files_deleted: int = 0
    compression_ratio: float = 0.0


class LoggingMetricsCollector:
    """Thread-safe metrics collector for the Logging Framework."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._entries = 0
        self._reports = 0
        self._bytes_written = 0
        self._bytes_compressed = 0
        self._files_rotated = 0
        self._files_deleted = 0
        self._compression_ratios: list[float] = []

    def entry_written(self, bytes_count: int = 0) -> None:
        with self._lock:
            self._entries += 1
            if bytes_count:
                self._bytes_written += bytes_count

    def report_generated(self) -> None:
        with self._lock:
            self._reports += 1

    def bytes_compressed(self, original: int, compressed: int) -> None:
        with self._lock:
            self._bytes_compressed += compressed
            if original:
                self._compression_ratios.append(compressed / original)

    def file_rotated(self) -> None:
        with self._lock:
            self._files_rotated += 1

    def file_deleted(self, _bytes_count: int = 0) -> None:
        with self._lock:
            self._files_deleted += 1

    def snapshot(self) -> LoggingMetricsSnapshot:
        with self._lock:
            ratio = 0.0
            if self._compression_ratios:
                ratio = sum(self._compression_ratios) / len(self._compression_ratios)
            return LoggingMetricsSnapshot(
                log_entries_written=self._entries,
                reports_generated=self._reports,
                bytes_written=self._bytes_written,
                bytes_compressed=self._bytes_compressed,
                files_rotated=self._files_rotated,
                files_deleted=self._files_deleted,
                compression_ratio=round(ratio, 2),
            )
