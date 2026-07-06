"""
Threat Engine — converts SecurityIncidents into ThreatAssessments.

No enforcement, no alerts, no reputation changes.
"""

from __future__ import annotations

import logging
import time

from security_agent.correlation.models import SecurityIncident
from security_agent.threat.assessor import assess_incident
from security_agent.threat.metrics import ThreatMetricsCollector, ThreatMetricsSnapshot
from security_agent.threat.models import ThreatAssessment

logger = logging.getLogger("threat")


class ThreatEngine:
    """Converts SecurityIncidents into ThreatAssessments.

    Usage:
        engine = ThreatEngine()
        assessment = engine.assess(incident, chain_severity=7)
    """

    def __init__(self) -> None:
        self._metrics = ThreatMetricsCollector()

    def assess(
        self,
        incident: SecurityIncident,
        chain_severity: int = 0,
        chain_confidence: int = 0,
        matched_rule_severities: list[int] | None = None,
    ) -> ThreatAssessment | None:
        """Assess a single incident and return a ThreatAssessment.

        Args:
            incident: SecurityIncident to assess.
            chain_severity: Severity from the attack chain definition.
            chain_confidence: Confidence modifier from the attack chain.
            matched_rule_severities: Severity values from matched rules.

        Returns:
            ThreatAssessment or None on error.
        """
        start = time.monotonic()

        try:
            assessment = assess_incident(
                incident=incident,
                chain_severity=chain_severity,
                chain_confidence=chain_confidence,
                matched_rule_severities=matched_rule_severities,
            )

            latency_ms = (time.monotonic() - start) * 1000
            self._metrics.assessment_completed(
                risk_level=int(assessment.risk_level),
                confidence=assessment.confidence,
                threat_score=assessment.threat_score,
                latency_ms=latency_ms,
            )

            logger.debug(
                "Threat assessed",
                extra={
                    "incident": incident.incident_id,
                    "threat_id": assessment.threat_id,
                    "risk": assessment.risk_level.name,
                    "score": assessment.threat_score,
                    "confidence": assessment.confidence,
                },
            )

            return assessment

        except Exception as e:
            self._metrics.error()
            logger.error(
                "Threat assessment failed",
                extra={"incident": incident.incident_id, "error": str(e)},
            )
            return None

    def assess_batch(
        self,
        incidents: list[SecurityIncident],
        chain_severities: dict[str, int] | None = None,
        chain_confidences: dict[str, int] | None = None,
    ) -> list[ThreatAssessment]:
        """Assess multiple incidents.

        Args:
            incidents: List of SecurityIncidents.
            chain_severities: Optional mapping of chain_id → severity.
            chain_confidences: Optional mapping of chain_id → confidence.

        Returns:
            List of ThreatAssessments (None results filtered out).
        """
        results: list[ThreatAssessment] = []
        for incident in incidents:
            sev = (chain_severities or {}).get(incident.attack_chain_id, 0)
            conf = (chain_confidences or {}).get(incident.attack_chain_id, 0)
            assessment = self.assess(
                incident, chain_severity=sev, chain_confidence=conf
            )
            if assessment is not None:
                results.append(assessment)
        return results

    def metrics_snapshot(self) -> ThreatMetricsSnapshot:
        return self._metrics.snapshot()
