"""Metrics collection for the Threat Engine."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class ThreatMetricsSnapshot:
    total_assessments: int = 0
    informational_count: int = 0
    low_count: int = 0
    medium_count: int = 0
    high_count: int = 0
    critical_count: int = 0
    avg_confidence: float = 0.0
    avg_threat_score: float = 0.0
    avg_assessment_latency_ms: float = 0.0
    max_assessment_latency_ms: float = 0.0
    errors: int = 0


class ThreatMetricsCollector:
    """Thread-safe metrics collector."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._total = 0
        self._informational = 0
        self._low = 0
        self._medium = 0
        self._high = 0
        self._critical = 0
        self._confidences: list[int] = []
        self._scores: list[int] = []
        self._latencies: list[float] = []
        self._errors = 0

    def assessment_completed(
        self,
        risk_level: int,
        confidence: int,
        threat_score: int,
        latency_ms: float,
    ) -> None:
        with self._lock:
            self._total += 1
            if risk_level == 0:
                self._informational += 1
            elif risk_level == 1:
                self._low += 1
            elif risk_level == 2:
                self._medium += 1
            elif risk_level == 3:
                self._high += 1
            elif risk_level == 4:
                self._critical += 1
            self._confidences.append(confidence)
            self._scores.append(threat_score)
            self._latencies.append(latency_ms)
            if len(self._confidences) > 10000:
                self._confidences = self._confidences[-10000:]
                self._scores = self._scores[-10000:]
                self._latencies = self._latencies[-10000:]

    def error(self) -> None:
        with self._lock:
            self._errors += 1

    def snapshot(self) -> ThreatMetricsSnapshot:
        with self._lock:
            avg_c = (
                sum(self._confidences) / len(self._confidences)
                if self._confidences
                else 0.0
            )
            avg_s = sum(self._scores) / len(self._scores) if self._scores else 0.0
            avg_l = (
                sum(self._latencies) / len(self._latencies) if self._latencies else 0.0
            )
            mx_l = max(self._latencies) if self._latencies else 0.0
            return ThreatMetricsSnapshot(
                total_assessments=self._total,
                informational_count=self._informational,
                low_count=self._low,
                medium_count=self._medium,
                high_count=self._high,
                critical_count=self._critical,
                avg_confidence=avg_c,
                avg_threat_score=avg_s,
                avg_assessment_latency_ms=avg_l,
                max_assessment_latency_ms=mx_l,
                errors=self._errors,
            )
