"""Metrics collection for the Database layer."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class DatabaseMetricsSnapshot:
    inserts: int = 0
    queries: int = 0
    updates: int = 0
    transactions: int = 0
    rollbacks: int = 0
    migrations_run: int = 0
    avg_query_latency_ms: float = 0.0
    is_connected: bool = False


class DatabaseMetricsCollector:
    """Thread-safe metrics collector."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._inserts = 0
        self._queries = 0
        self._updates = 0
        self._transactions = 0
        self._rollbacks = 0
        self._migrations = 0
        self._latencies: list[float] = []

    def insert(self) -> None:
        with self._lock:
            self._inserts += 1

    def query(self) -> None:
        with self._lock:
            self._queries += 1

    def update(self) -> None:
        with self._lock:
            self._updates += 1

    def transaction(self) -> None:
        with self._lock:
            self._transactions += 1

    def rollback(self) -> None:
        with self._lock:
            self._rollbacks += 1

    def migration(self) -> None:
        with self._lock:
            self._migrations += 1

    def record_latency(self, seconds: float) -> None:
        with self._lock:
            self._latencies.append(seconds * 1000)
            if len(self._latencies) > 10000:
                self._latencies = self._latencies[-10000:]

    def snapshot(self, connected: bool = False) -> DatabaseMetricsSnapshot:
        with self._lock:
            avg = (
                sum(self._latencies) / len(self._latencies) if self._latencies else 0.0
            )
            return DatabaseMetricsSnapshot(
                inserts=self._inserts,
                queries=self._queries,
                updates=self._updates,
                transactions=self._transactions,
                rollbacks=self._rollbacks,
                migrations_run=self._migrations,
                avg_query_latency_ms=avg,
                is_connected=connected,
            )
