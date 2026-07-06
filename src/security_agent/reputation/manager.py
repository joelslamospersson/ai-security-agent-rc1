"""
Reputation manager — high-level operations on reputation records.

Coordinates scoring, decay, and storage.
No enforcement occurs here.
"""

from __future__ import annotations

import logging

from security_agent.reputation.decay import calculate_decay
from security_agent.reputation.models import EntityType, ReputationRecord
from security_agent.reputation.scoring import (
    calculate_positive_change,
    calculate_score_change,
    clamp_score,
)
from security_agent.reputation.store import ReputationStore

logger = logging.getLogger("reputation.manager")


class ReputationManager:
    """High-level reputation operations.

    Usage:
        manager = ReputationManager(store)
        record = manager.process_threat(entity_type, entity_value, threat_score, confidence, risk_level, ...)
        all_records = manager.list_all()
    """

    def __init__(self, store: ReputationStore) -> None:
        self._store = store

    def process_threat(
        self,
        entity_type: EntityType,
        entity_value: str,
        threat_score: int,
        confidence: int,
        risk_level: int,
        is_repeat: bool = False,
        ban_count: int = 0,
    ) -> ReputationRecord:
        """Process a threat assessment and update reputation.

        Returns the updated ReputationRecord.
        """
        existing = self._store.lookup(entity_type, entity_value)

        if existing:
            decayed = calculate_decay(
                current_score=existing.current_score,
                last_seen=existing.last_seen,
            )
        else:
            decayed = 0

        score_change = calculate_score_change(
            threat_score=threat_score,
            confidence=confidence,
            risk_level=risk_level,
            is_repeat=is_repeat,
            ban_count=ban_count,
        )

        positive = calculate_positive_change(
            existing.event_count if existing else 0,
        )

        new_score = clamp_score(decayed + score_change + positive)

        record = self._store.upsert(
            entity_type=entity_type,
            entity_value=entity_value,
            new_score=new_score,
            confidence=confidence,
            ban_count=ban_count,
        )

        logger.debug(
            "Reputation updated",
            extra={
                "entity": f"{entity_type.value}:{entity_value}",
                "score": new_score,
                "change": score_change,
                "threat_score": threat_score,
            },
        )

        return record

    def process_positive(
        self,
        entity_type: EntityType,
        entity_value: str,
        points: int = 1,
    ) -> ReputationRecord:
        """Increase reputation for legitimate activity."""
        existing = self._store.lookup(entity_type, entity_value)
        if existing:
            new_score = clamp_score(existing.current_score + points)
        else:
            new_score = points

        return self._store.upsert(
            entity_type=entity_type,
            entity_value=entity_value,
            new_score=new_score,
            confidence=50,
        )

    def get_reputation(
        self, entity_type: EntityType, entity_value: str
    ) -> ReputationRecord | None:
        return self._store.lookup(entity_type, entity_value)

    def exists(self, entity_type: EntityType, entity_value: str) -> bool:
        return bool(self._store.exists(entity_type, entity_value))

    def list_all(self) -> list[ReputationRecord]:
        return list(self._store.list_all())

    def apply_decay(self) -> int:
        """Apply decay to all entities. Returns count decayed."""
        count = 0
        for record in self._store.list_all():
            decayed = calculate_decay(
                current_score=record.current_score,
                last_seen=record.last_seen,
            )
            if decayed != record.current_score:
                self._store.upsert(
                    entity_type=record.entity_type,
                    entity_value=record.entity_value,
                    new_score=decayed,
                    confidence=record.confidence,
                    ban_count=record.ban_count,
                )
                count += 1
        return int(count)
