"""
Reputation Engine — maintains long-term security memory.

Input: ThreatAssessment
Output: Updated ReputationRecord

No enforcement occurs here.
"""

from __future__ import annotations

import logging

from security_agent.reputation.manager import ReputationManager
from security_agent.reputation.metrics import (
    ReputationMetricsCollector,
    ReputationMetricsSnapshot,
)
from security_agent.reputation.models import EntityType, ReputationRecord
from security_agent.reputation.store import ReputationStore

logger = logging.getLogger("reputation.engine")


class ReputationEngine:
    """Maintains long-term reputation for all tracked entities.

    Usage:
        engine = ReputationEngine()
        engine.process_threat(entity_type, entity_value, threat_score, ...)
        engine.apply_decay()
    """

    def __init__(self) -> None:
        self._store = ReputationStore()
        self._manager = ReputationManager(self._store)
        self._metrics = ReputationMetricsCollector()

    def process_threat(
        self,
        entity_type: EntityType,
        entity_value: str,
        threat_score: int,
        confidence: int,
        risk_level: int,
        is_repeat: bool = False,
        ban_count: int = 0,
    ) -> ReputationRecord | None:
        """Process a threat and update reputation.

        Returns updated ReputationRecord or None on error.
        """
        try:
            record = self._manager.process_threat(
                entity_type=entity_type,
                entity_value=entity_value,
                threat_score=threat_score,
                confidence=confidence,
                risk_level=risk_level,
                is_repeat=is_repeat,
                ban_count=ban_count,
            )
            self._metrics.update()
            return record
        except Exception as e:
            logger.error(
                "Reputation update failed",
                extra={
                    "entity": f"{entity_type.value}:{entity_value}",
                    "error": str(e),
                },
            )
            return None

    def process_positive(
        self,
        entity_type: EntityType,
        entity_value: str,
        points: int = 1,
    ) -> ReputationRecord | None:
        """Increase reputation for legitimate activity."""
        try:
            record = self._manager.process_positive(
                entity_type=entity_type,
                entity_value=entity_value,
                points=points,
            )
            self._metrics.update()
            return record
        except Exception as e:
            logger.error(
                "Positive reputation update failed",
                extra={
                    "entity": f"{entity_type.value}:{entity_value}",
                    "error": str(e),
                },
            )
            return None

    def get_reputation(
        self,
        entity_type: EntityType,
        entity_value: str,
    ) -> ReputationRecord | None:
        self._metrics.lookup()
        return self._manager.get_reputation(entity_type, entity_value)

    def exists(self, entity_type: EntityType, entity_value: str) -> bool:
        return bool(self._manager.exists(entity_type, entity_value))

    def list_all(self) -> list[ReputationRecord]:
        return list(self._manager.list_all())

    def apply_decay(self) -> int:
        """Apply decay to all entities. Returns count."""
        count = self._manager.apply_decay()
        if count > 0:
            self._metrics.decay()
            logger.debug("Decay applied", extra={"entities": count})
        return int(count)

    def metrics_snapshot(self) -> ReputationMetricsSnapshot:
        return self._metrics.snapshot(self._store.list_all())
