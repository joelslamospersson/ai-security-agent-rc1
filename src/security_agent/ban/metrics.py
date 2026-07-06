"""Metrics collection for the Ban Engine."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class BanMetricsSnapshot:
    total_decisions: int = 0
    warnings: int = 0
    temporary_bans: int = 0
    permanent_bans: int = 0
    whitelist_skips: int = 0
    exemption_skips: int = 0
    avg_threat_score: float = 0.0
    avg_confidence: float = 0.0
    avg_duration_seconds: float = 0.0
    escalation_rate: float = 0.0


class BanMetricsCollector:
    """Thread-safe metrics collector."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._total = 0
        self._warnings = 0
        self._temp_bans = 0
        self._perm_bans = 0
        self._whitelist = 0
        self._exempt = 0
        self._threat_scores: list[int] = []
        self._confidences: list[int] = []
        self._durations: list[int] = []
        self._escalations: list[int] = []

    def record_decision(
        self,
        action: str,
        threat: int,
        conf: int,
        duration: int,
        level: int,
    ) -> None:
        with self._lock:
            self._total += 1
            if action == "warning":
                self._warnings += 1
            elif action == "temporary_ban":
                self._temp_bans += 1
            elif action == "permanent_ban":
                self._perm_bans += 1
            elif action == "whitelist_skip":
                self._whitelist += 1
            elif action == "exemption_skip":
                self._exempt += 1
            self._threat_scores.append(threat)
            self._confidences.append(conf)
            self._durations.append(duration)
            self._escalations.append(level)
            for lst in [
                self._threat_scores,
                self._confidences,
                self._durations,
                self._escalations,
            ]:
                if len(lst) > 10000:
                    lst[:] = lst[-10000:]

    def snapshot(self) -> BanMetricsSnapshot:
        with self._lock:
            n = self._total or 1
            return BanMetricsSnapshot(
                total_decisions=self._total,
                warnings=self._warnings,
                temporary_bans=self._temp_bans,
                permanent_bans=self._perm_bans,
                whitelist_skips=self._whitelist,
                exemption_skips=self._exempt,
                avg_threat_score=sum(self._threat_scores) / n,
                avg_confidence=sum(self._confidences) / n,
                avg_duration_seconds=sum(self._durations) / n,
                escalation_rate=len(self._escalations) / n,
            )
