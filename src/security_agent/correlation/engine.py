"""
Correlation Engine — correlates RuleMatches into security incidents.

Input: RuleMatch objects
Output: SecurityIncident objects

No enforcement, no reputation changes, no alerting.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from security_agent.correlation.chain import ChainTracker
from security_agent.correlation.incident import IncidentManager
from security_agent.correlation.matcher import extract_key_value
from security_agent.correlation.metrics import (
    CorrelationMetricsCollector,
    CorrelationMetricsSnapshot,
)
from security_agent.correlation.models import (
    AttackChain,
    SecurityIncident,
)

logger = logging.getLogger("correlation")


class CorrelationEngine:
    """Correlates RuleMatches into SecurityIncidents.

    Usage:
        engine = CorrelationEngine()
        engine.load_chains(attack_chains)
        incidents = engine.correlate(rule_match, event_data)
        await engine.cleanup_expired()
    """

    def __init__(self) -> None:
        self._chain_defs: dict[str, AttackChain] = {}
        self._tracker = ChainTracker()
        self._incidents = IncidentManager()
        self._metrics = CorrelationMetricsCollector()

    def load_chains(self, chains: list[AttackChain]) -> None:
        """Load attack chain definitions."""
        for chain in chains:
            if chain.enabled:
                self._chain_defs[chain.id] = chain
        logger.info(
            "Attack chains loaded",
            extra={"total": len(chains), "enabled": len(self._chain_defs)},
        )

    def correlate(
        self,
        rule_match: Any,
        event_data: dict[str, Any] | None = None,
    ) -> list[SecurityIncident]:
        """Correlate a RuleMatch against all attack chains.

        Args:
            rule_match: A RuleMatch object (must have rule_id attribute).
            event_data: Optional event dict for extracting correlation keys.

        Returns:
            List of new SecurityIncidents (empty if no chain completed).
        """
        start = time.monotonic()
        new_incidents: list[SecurityIncident] = []
        rule_id = getattr(rule_match, "rule_id", "") or ""
        event_id = getattr(rule_match, "event_id", "") or ""

        for chain_def in self._chain_defs.values():
            try:
                key_value = extract_key_value(
                    chain_def.correlation_key,
                    rule_match,
                    event_data,
                )
                if key_value == "unknown":
                    continue

                active = self._tracker.get_chain(chain_def.id, key_value)
                if active is None:
                    active = self._tracker.start_chain(chain_def, key_value)
                    self._metrics.chain_started()

                self._metrics.chain_advanced()
                completed = self._tracker.advance(
                    chain_def,
                    active,
                    rule_id,
                    event_id,
                )

                if completed:
                    incident = self._incidents.create_incident(
                        chain_def,
                        active,
                    )
                    new_incidents.append(incident)
                    self._metrics.chain_completed()
                    self._tracker.remove(chain_def.id, key_value)
                    logger.info(
                        "Attack chain completed",
                        extra={
                            "chain": chain_def.id,
                            "key": key_value,
                            "incident": incident.incident_id,
                        },
                    )

            except Exception as e:
                self._metrics.error()
                logger.error(
                    "Correlation error",
                    extra={"chain": chain_def.id, "error": str(e)},
                )

        elapsed = time.monotonic() - start
        self._metrics.record_latency(elapsed)
        return new_incidents

    async def cleanup_expired(self) -> list[SecurityIncident]:
        """Expire old chains and return their incidents."""
        expired_active = await self._tracker.expire_old(self._chain_defs)
        expired_incidents = self._incidents.expire_incidents(expired_active)
        for ac in expired_active:
            self._metrics.chain_expired()
            logger.debug(
                "Chain expired", extra={"chain": ac.chain_id, "key": ac.key_value}
            )
        return list(expired_incidents)

    @property
    def active_count(self) -> int:
        return int(self._tracker.active_count)

    @property
    def incident_count(self) -> int:
        return int(self._incidents.incident_count)

    def metrics_snapshot(self) -> CorrelationMetricsSnapshot:
        return self._metrics.snapshot()

    def clear(self) -> None:
        self._chain_defs.clear()
        self._tracker.clear()
        self._incidents.clear()
