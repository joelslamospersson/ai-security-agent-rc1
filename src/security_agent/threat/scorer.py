"""
Deterministic threat scoring engine.

All scoring is deterministic. No machine learning, no AI.
"""

from __future__ import annotations

from security_agent.threat.models import RISK_THRESHOLDS, RecommendedAction, RiskLevel


def calculate_threat_score(
    incident_confidence: int,
    matched_stages: int,
    total_stages: int,
    max_severity: int,
    modifier: int = 0,
) -> int:
    """Calculate a deterministic threat score (0-100)."""
    confidence_part = incident_confidence * 0.4
    completion_ratio = (matched_stages / max(total_stages, 1)) * 30.0
    severity_part = (max_severity / 10.0) * 20.0
    modifier_part = modifier * 0.1
    score = confidence_part + completion_ratio + severity_part + modifier_part
    return max(0, min(100, round(score)))


def calculate_confidence(
    incident_confidence: int,
    chain_confidence_modifier: int,
    matched_rules_count: int,
) -> int:
    """Calculate overall confidence (0-100) from multiple signals."""
    base = float(incident_confidence)
    chain_mod = float(chain_confidence_modifier)
    rule_bonus = min(float(matched_rules_count) * 2.0, 20.0)
    result = base + chain_mod + rule_bonus
    return max(0, min(100, round(result)))


def calculate_severity(chain_severity: int, max_rule_severity: int) -> int:
    """Calculate severity (0-10) as max of chain and rule severities."""
    return max(0, min(10, max(chain_severity, max_rule_severity)))


def classify_risk(threat_score: int) -> RiskLevel:
    """Map threat score to risk level using configurable thresholds."""
    for level, (lo, hi) in sorted(
        RISK_THRESHOLDS.items(), key=lambda x: x[0], reverse=True
    ):
        if lo <= threat_score <= hi:
            return level
    return RiskLevel.INFORMATIONAL


def recommend_action(
    risk_level: RiskLevel,
    confidence: int,
    chain_completed: bool,
) -> tuple[RecommendedAction, str]:
    """Recommend an action based on threat assessment."""
    if risk_level == RiskLevel.CRITICAL and confidence >= 70:
        if chain_completed:
            return RecommendedAction.PERMANENT_BAN, "Critical completed attack chain"
        return RecommendedAction.TEMPORARY_BAN, "Critical threat detected"

    if risk_level == RiskLevel.HIGH and confidence >= 60:
        return RecommendedAction.TEMPORARY_BAN, "High confidence threat"

    if risk_level == RiskLevel.MEDIUM:
        if confidence >= 50:
            return (
                RecommendedAction.NOTIFY_ADMIN,
                "Medium confidence threat requires review",
            )
        return RecommendedAction.MONITOR, "Medium threat, continue monitoring"

    if risk_level == RiskLevel.LOW:
        return RecommendedAction.MONITOR, "Low level threat, continue monitoring"

    return RecommendedAction.IGNORE, "Informational only, no action needed"
