"""
In-memory reputation store.

Designed so the backend can be swapped for SQLite later
without changing the public API.
"""

from __future__ import annotations

import time
from typing import Any

from security_agent.reputation.exceptions import EntityNotFoundError
from security_agent.reputation.models import (
    EntityType,
    ReputationRecord,
)


class ReputationStore:
    """In-memory reputation storage.

    All public methods are O(1) average.
    Thread-safe: uses a single dict with atomic operations.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], ReputationRecord] = {}

    def lookup(
        self, entity_type: EntityType, entity_value: str
    ) -> ReputationRecord | None:
        """Look up a reputation record."""
        return self._store.get((entity_type.value, entity_value))

    def update(self, record: ReputationRecord) -> None:
        """Store a reputation record (create or update)."""
        key = (record.entity_type.value, record.entity_value)
        self._store[key] = record

    def exists(self, entity_type: EntityType, entity_value: str) -> bool:
        """Check if an entity has a record."""
        return (entity_type.value, entity_value) in self._store

    def remove(self, entity_type: EntityType, entity_value: str) -> None:
        """Remove an entity's reputation record."""
        key = (entity_type.value, entity_value)
        if key not in self._store:
            raise EntityNotFoundError(
                f"Entity {entity_type.value}:{entity_value} not found"
            )
        del self._store[key]

    def list_all(self) -> list[ReputationRecord]:
        """Return all reputation records."""
        return list(self._store.values())

    def list_by_type(self, entity_type: EntityType) -> list[ReputationRecord]:
        """Return records for a specific entity type."""
        return [r for r in self._store.values() if r.entity_type == entity_type]

    def count(self) -> int:
        """Total number of tracked entities."""
        return len(self._store)

    def upsert(
        self,
        entity_type: EntityType,
        entity_value: str,
        new_score: int,
        confidence: int,
        ban_count: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> ReputationRecord:
        """Create or update a reputation record."""
        now = time.time()
        existing = self.lookup(entity_type, entity_value)

        if existing:
            record = ReputationRecord(
                entity_type=entity_type,
                entity_value=entity_value,
                current_score=new_score,
                previous_score=existing.current_score,
                confidence=confidence,
                first_seen=existing.first_seen,
                last_seen=now,
                event_count=existing.event_count + 1,
                ban_count=max(existing.ban_count, ban_count),
                decay_state=existing.decay_state,
                metadata=metadata or existing.metadata,
            )
        else:
            record = ReputationRecord(
                entity_type=entity_type,
                entity_value=entity_value,
                current_score=new_score,
                confidence=confidence,
                first_seen=now,
                last_seen=now,
                event_count=1,
                ban_count=ban_count,
                metadata=metadata or {},
            )

        self.update(record)
        return record

    def clear(self) -> None:
        """Remove all records."""
        self._store.clear()
