"""
Policy metrics — thread-safe counters for the Policy Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class PolicyMetricsSnapshot:
    loaded_policies: int = 0
    validation_failures: int = 0
    policy_assignments: int = 0
    overrides: int = 0
    inheritance_depth: int = 0
    reloads: int = 0


class PolicyMetricsCollector:
    """Thread-safe metrics collector for the Policy Engine."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._validation_failures = 0
        self._assignments = 0
        self._overrides = 0
        self._reloads = 0

    def validation_failure(self) -> None:
        with self._lock:
            self._validation_failures += 1

    def assignment(self) -> None:
        with self._lock:
            self._assignments += 1

    def override(self) -> None:
        with self._lock:
            self._overrides += 1

    def reload(self) -> None:
        with self._lock:
            self._reloads += 1

    def snapshot(
        self,
        loaded_policies: int = 0,
        inheritance_depth: int = 0,
    ) -> PolicyMetricsSnapshot:
        with self._lock:
            return PolicyMetricsSnapshot(
                loaded_policies=loaded_policies,
                validation_failures=self._validation_failures,
                policy_assignments=self._assignments,
                overrides=self._overrides,
                inheritance_depth=inheritance_depth,
                reloads=self._reloads,
            )
