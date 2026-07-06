"""
Ban Engine — makes ban decisions based on threats and reputation.

Never performs enforcement. No iptables, nftables, or firewall calls.
"""

from __future__ import annotations

import logging
from typing import Any

from security_agent.ban.decision import make_decision
from security_agent.ban.history import BanHistory
from security_agent.ban.metrics import BanMetricsCollector, BanMetricsSnapshot
from security_agent.ban.models import BanDecision

logger = logging.getLogger("ban.engine")


class BanEngine:
    """Makes ban decisions. Never enforces them.

    Usage:
        engine = BanEngine()
        decision = engine.decide(
            entity="1.2.3.4", entity_type="ipv4",
            threat_score=85, confidence=90, reputation_score=-60,
        )
    """

    def __init__(self) -> None:
        self._history = BanHistory()
        self._whitelist: set[tuple[str, str]] = set()
        self._exemptions: set[tuple[str, str]] = set()
        self._metrics = BanMetricsCollector()

    def decide(
        self,
        entity: str,
        entity_type: str = "ipv4",
        threat_score: int = 0,
        confidence: int = 0,
        reputation_score: int = 0,
        correlation_id: str = "",
        policy_name: str = "balanced",
    ) -> BanDecision:
        """Make a ban decision.

        Args:
            entity: The entity to evaluate (IP, username, etc.).
            entity_type: Type of entity (ipv4, username, hostname, etc.).
            threat_score: 0-100 from threat assessment.
            confidence: 0-100 from threat assessment.
            reputation_score: -100 to 100 from reputation engine.
            correlation_id: Correlation ID for event chain.
            policy_name: Name of the ban policy to use.

        Returns:
            BanDecision (never executed).
        """
        whitelisted = (entity_type, entity) in self._whitelist
        exempt = (entity_type, entity) in self._exemptions

        decision = make_decision(
            entity=entity,
            entity_type=entity_type,
            threat_score=threat_score,
            confidence=confidence,
            reputation_score=reputation_score,
            correlation_id=correlation_id,
            history=self._history,
            policy_name=policy_name,
            whitelisted=whitelisted,
            exempt=exempt,
        )

        # Record in history for actual bans
        if decision.action in ("temporary_ban", "permanent_ban", "warning"):
            self._history.record_ban(
                entity=entity,
                entity_type=entity_type,
                level=int(decision.escalation_level),
                duration=decision.ban_duration,
            )

        self._metrics.record_decision(
            action=decision.action.value,
            threat=threat_score,
            conf=confidence,
            duration=decision.ban_duration,
            level=int(decision.escalation_level),
        )

        if (
            decision.action.value != "whitelist_skip"
            and decision.action.value != "exemption_skip"
        ):
            logger.info(
                "Ban decision made",
                extra={
                    "entity": entity,
                    "action": decision.action.value,
                    "threat": threat_score,
                    "confidence": confidence,
                    "reason": decision.reason,
                },
            )

        return decision

    def whitelist_add(self, entity: str, entity_type: str = "ipv4") -> None:
        """Add an entity to the whitelist."""
        self._whitelist.add((entity_type, entity))

    def whitelist_remove(self, entity: str, entity_type: str = "ipv4") -> None:
        """Remove an entity from the whitelist."""
        self._whitelist.discard((entity_type, entity))

    def is_whitelisted(self, entity: str, entity_type: str = "ipv4") -> bool:
        return (entity_type, entity) in self._whitelist

    def exemption_add(self, entity: str, entity_type: str = "ipv4") -> None:
        """Add an exempt entity."""
        self._exemptions.add((entity_type, entity))

    def exemption_remove(self, entity: str, entity_type: str = "ipv4") -> None:
        self._exemptions.discard((entity_type, entity))

    def is_exempt(self, entity: str, entity_type: str = "ipv4") -> bool:
        return (entity_type, entity) in self._exemptions

    def get_ban_history(self, entity: str, entity_type: str = "ipv4") -> Any:
        return self._history.lookup(entity, entity_type)

    def metrics_snapshot(self) -> BanMetricsSnapshot:
        return self._metrics.snapshot()
