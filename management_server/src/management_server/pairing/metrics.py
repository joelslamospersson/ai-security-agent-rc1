"""
Pairing metrics — thread-safe counters for the secure pairing protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class PairingMetricsSnapshot:
    """Snapshot of pairing metrics."""

    tokens_generated: int = 0
    tokens_consumed: int = 0
    tokens_expired: int = 0
    tokens_revoked: int = 0
    validation_failures: int = 0
    replay_attempts: int = 0
    active_tokens: int = 0
    total_tokens: int = 0


class PairingMetricsCollector:
    """Thread-safe metrics collector for the pairing subsystem."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._generated = 0
        self._consumed = 0
        self._expired = 0
        self._revoked = 0
        self._validation_failures = 0
        self._replay_attempts = 0

    def token_generated(self) -> None:
        with self._lock:
            self._generated += 1

    def token_consumed(self) -> None:
        with self._lock:
            self._consumed += 1

    def token_expired(self) -> None:
        with self._lock:
            self._expired += 1

    def token_revoked(self) -> None:
        with self._lock:
            self._revoked += 1

    def validation_failure(self) -> None:
        with self._lock:
            self._validation_failures += 1

    def replay_attempt(self) -> None:
        with self._lock:
            self._replay_attempts += 1

    def snapshot(self, active_tokens: int = 0, total_tokens: int = 0) -> PairingMetricsSnapshot:
        with self._lock:
            return PairingMetricsSnapshot(
                tokens_generated=self._generated,
                tokens_consumed=self._consumed,
                tokens_expired=self._expired,
                tokens_revoked=self._revoked,
                validation_failures=self._validation_failures,
                replay_attempts=self._replay_attempts,
                active_tokens=active_tokens,
                total_tokens=total_tokens,
            )
