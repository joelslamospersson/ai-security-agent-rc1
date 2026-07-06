"""
Audit retention — configurable retention policy calculation.

No automatic cleanup — only calculation and reporting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import structlog

from management_server.audit.models import RetentionPolicy

logger = structlog.get_logger("audit.retention")


@dataclass
class RetentionReport:
    """Report of retention analysis."""

    total_events: int = 0
    events_to_retain: int = 0
    events_to_purge: int = 0
    purge_before: datetime | None = None
    policy_days: int = 365
    exceeds_max_records: bool = False
    record_overage: int = 0


class RetentionCalculator:
    """Calculates retention metrics without performing deletion."""

    def __init__(self, policy: RetentionPolicy | None = None) -> None:
        self._policy = policy or RetentionPolicy()

    def analyze(
        self, total_events: int, oldest_event_timestamp: datetime | None = None
    ) -> RetentionReport:
        """Analyze retention and return a report."""
        cutoff = self._policy.cutoff_date

        events_to_purge = 0
        if oldest_event_timestamp and oldest_event_timestamp < cutoff:
            estimated_age = (cutoff - oldest_event_timestamp).days
            events_to_purge = min(total_events, max(0, estimated_age))

        exceeds = total_events > self._policy.max_records
        overage = max(0, total_events - self._policy.max_records) if exceeds else 0

        return RetentionReport(
            total_events=total_events,
            events_to_retain=max(0, total_events - events_to_purge),
            events_to_purge=events_to_purge,
            purge_before=cutoff,
            policy_days=self._policy.retention_days,
            exceeds_max_records=exceeds,
            record_overage=overage,
        )

    @property
    def policy(self) -> RetentionPolicy:
        return self._policy

    @staticmethod
    def default_policy() -> RetentionPolicy:
        return RetentionPolicy(retention_days=365, max_records=1_000_000)
