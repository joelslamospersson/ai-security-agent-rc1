"""
Metrics collection for the Pipeline Engine.

Tracks pipeline throughput, stage latencies, retry counts,
and error rates. Integrates with the existing BusMetricsCollector
pattern and will be subsumed by the centralized Metrics subsystem
in a later phase.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class PipelineMetricsSnapshot:
    """Snapshot of pipeline metrics at a point in time."""

    active_pipelines: int = 0
    events_processed: int = 0
    events_dropped: int = 0
    events_cancelled: int = 0
    stages_failed: int = 0
    total_retries: int = 0
    stage_latency_ms: float = 0.0
    pipeline_latency_ms: float = 0.0
    queue_wait_ms: float = 0.0
    events_per_second: float = 0.0
    stage_names: list[str] = field(default_factory=list)


class PipelineMetricsCollector:
    """Collects metrics for the Pipeline Engine.

    Thread-safe. Uses Lock for counter updates.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._events_processed: int = 0
        self._events_dropped: int = 0
        self._events_cancelled: int = 0
        self._stages_failed: int = 0
        self._total_retries: int = 0
        self._stage_latencies: dict[str, list[float]] = {}
        self._pipeline_latencies: list[float] = []
        self._queue_wait_times: list[float] = []
        self._active_pipelines: int = 0
        self._peak_active: int = 0
        self._start_time: float = time.monotonic()

    def increment_processed(self, count: int = 1) -> None:
        with self._lock:
            self._events_processed += count

    def increment_dropped(self, count: int = 1) -> None:
        with self._lock:
            self._events_dropped += count

    def increment_cancelled(self, count: int = 1) -> None:
        with self._lock:
            self._events_cancelled += count

    def increment_failed(self, count: int = 1) -> None:
        with self._lock:
            self._stages_failed += count

    def increment_retries(self, count: int = 1) -> None:
        with self._lock:
            self._total_retries += count

    def record_stage_latency(self, stage: str, seconds: float) -> None:
        with self._lock:
            if stage not in self._stage_latencies:
                self._stage_latencies[stage] = []
            self._stage_latencies[stage].append(seconds * 1000)
            vals = self._stage_latencies[stage]
            if len(vals) > 1000:
                self._stage_latencies[stage] = vals[-1000:]

    def record_pipeline_latency(self, seconds: float) -> None:
        with self._lock:
            self._pipeline_latencies.append(seconds * 1000)
            if len(self._pipeline_latencies) > 1000:
                self._pipeline_latencies = self._pipeline_latencies[-1000:]

    def record_queue_wait(self, seconds: float) -> None:
        with self._lock:
            self._queue_wait_times.append(seconds * 1000)
            if len(self._queue_wait_times) > 1000:
                self._queue_wait_times = self._queue_wait_times[-1000:]

    def pipeline_started(self) -> None:
        with self._lock:
            self._active_pipelines += 1
            if self._active_pipelines > self._peak_active:
                self._peak_active = self._active_pipelines

    def pipeline_finished(self) -> None:
        with self._lock:
            self._active_pipelines -= 1

    def snapshot(self, stage_names: list[str] | None = None) -> PipelineMetricsSnapshot:
        with self._lock:
            elapsed = time.monotonic() - self._start_time
            eps = self._events_processed / elapsed if elapsed > 0 else 0.0

            all_stage_lats: list[float] = []
            for lats in self._stage_latencies.values():
                all_stage_lats.extend(lats)

            avg_stage = (
                sum(all_stage_lats) / len(all_stage_lats) if all_stage_lats else 0.0
            )
            avg_pipeline = (
                sum(self._pipeline_latencies) / len(self._pipeline_latencies)
                if self._pipeline_latencies
                else 0.0
            )
            avg_queue = (
                sum(self._queue_wait_times) / len(self._queue_wait_times)
                if self._queue_wait_times
                else 0.0
            )

            return PipelineMetricsSnapshot(
                active_pipelines=self._active_pipelines,
                events_processed=self._events_processed,
                events_dropped=self._events_dropped,
                events_cancelled=self._events_cancelled,
                stages_failed=self._stages_failed,
                total_retries=self._total_retries,
                stage_latency_ms=avg_stage,
                pipeline_latency_ms=avg_pipeline,
                queue_wait_ms=avg_queue,
                events_per_second=round(eps, 1),
                stage_names=stage_names or [],
            )
