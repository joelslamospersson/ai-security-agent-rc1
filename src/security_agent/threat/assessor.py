"""
Threat assessor — converts SecurityIncidents into ThreatAssessments.

No enforcement occurs here.
"""

from __future__ import annotations

from security_agent.correlation.models import SecurityIncident
from security_agent.threat.models import ThreatAssessment
from security_agent.threat.scorer import (
    calculate_confidence,
    calculate_severity,
    calculate_threat_score,
    classify_risk,
    recommend_action,
)


def assess_incident(
    incident: SecurityIncident,
    chain_severity: int = 0,
    chain_confidence: int = 0,
    matched_rule_severities: list[int] | None = None,
) -> ThreatAssessment:
    """Convert a SecurityIncident into a ThreatAssessment.

    Args:
        incident: The SecurityIncident to assess.
        chain_severity: Severity from the attack chain definition.
        chain_confidence: Confidence modifier from the attack chain.
        matched_rule_severities: Severity values from matched rules.

    Returns:
        Immutable ThreatAssessment with scores, risk level, and action.
    """
    max_rule_sev = max(matched_rule_severities) if matched_rule_severities else 0
    modifier = incident.confidence_modifier

    severity = calculate_severity(chain_severity, max_rule_sev)
    confidence = calculate_confidence(
        int(modifier),
        chain_confidence,
        len(incident.matched_rules),
    )
    threat_score = calculate_threat_score(
        incident_confidence=confidence,
        matched_stages=incident.progress // 10 if incident.progress > 0 else 0,
        total_stages=10,
        max_severity=severity,
        modifier=modifier,
    )
    chain_completed = incident.state.name == "COMPLETED"
    risk_level = classify_risk(threat_score)
    action, reason = recommend_action(risk_level, confidence, chain_completed)

    return ThreatAssessment(
        incident_id=incident.incident_id,
        correlation_id=incident.correlation_id,
        confidence=confidence,
        threat_score=threat_score,
        severity=severity,
        risk_level=risk_level,
        matched_rules=incident.matched_rules,
        attack_chain_ids=(incident.attack_chain_id,)
        if incident.attack_chain_id
        else (),
        matched_stages=incident.progress // 10,
        total_stages=10,
        recommended_action=action,
        action_reason=reason,
        metadata={
            "incident_state": incident.state.name,
            "chain_completed": chain_completed,
            "matched_events_count": len(incident.matched_events),
        },
    )
