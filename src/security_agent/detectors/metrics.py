"""Metrics collection for the Detection Framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class DetectorMetricsSnapshot:
    events_analyzed: int = 0
    events_skipped: int = 0
    analyses_failed: int = 0
    detections_produced: int = 0
    active_detectors: int = 0
    registered_detectors: int = 0
    enabled_detectors: int = 0
    disabled_detectors: int = 0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    detector_names: list[str] = field(default_factory=list)


class DetectorMetricsCollector:
    """Thread-safe metrics collector for the Detection Framework."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._events_analyzed = 0
        self._events_skipped = 0
        self._analyses_failed = 0
        self._detections_produced = 0
        self._latencies: list[float] = []

    def event_analyzed(self) -> None:
        with self._lock:
            self._events_analyzed += 1

    def event_skipped(self) -> None:
        with self._lock:
            self._events_skipped += 1

    def analysis_failed(self) -> None:
        with self._lock:
            self._analyses_failed += 1

    def detections(self, count: int = 1) -> None:
        with self._lock:
            self._detections_produced += count

    def record_latency(self, seconds: float) -> None:
        with self._lock:
            ms = seconds * 1000
            self._latencies.append(ms)
            if len(self._latencies) > 1000:
                self._latencies = self._latencies[-1000:]

    def snapshot(
        self,
        registered: int = 0,
        enabled: int = 0,
        names: list[str] | None = None,
    ) -> DetectorMetricsSnapshot:
        with self._lock:
            avg = (
                sum(self._latencies) / len(self._latencies) if self._latencies else 0.0
            )
            mx = max(self._latencies) if self._latencies else 0.0
            return DetectorMetricsSnapshot(
                events_analyzed=self._events_analyzed,
                events_skipped=self._events_skipped,
                analyses_failed=self._analyses_failed,
                detections_produced=self._detections_produced,
                active_detectors=enabled,
                registered_detectors=registered,
                enabled_detectors=enabled,
                disabled_detectors=registered - enabled,
                avg_latency_ms=avg,
                max_latency_ms=mx,
                detector_names=names or [],
            )
