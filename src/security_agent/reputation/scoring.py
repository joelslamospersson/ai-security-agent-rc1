"""
Deterministic reputation scoring.
"""

from __future__ import annotations

from security_agent.reputation.models import REPUTATION_MAX, REPUTATION_MIN


def calculate_score_change(
    threat_score: int,
    confidence: int,
    risk_level: int,
    is_repeat: bool,
    ban_count: int,
) -> int:
    """Calculate how much reputation should change.

    Returns negative values for threats, positive for legitimate activity.
    """
    base = -(threat_score / 100.0) * 30.0
    confidence_factor = (confidence / 100.0) * 1.5
    penalty = base * confidence_factor

    if is_repeat:
        penalty *= 1.5
    if ban_count > 0:
        penalty *= min(1.0 + (ban_count * 0.25), 3.0)
    if risk_level >= 3:
        penalty *= 1.3

    result = int(round(penalty))
    clamped = max(REPUTATION_MIN, min(REPUTATION_MAX, result))
    return int(clamped)


def calculate_positive_change(event_count: int) -> int:
    """Small positive adjustment for legitimate activity."""
    if event_count > 0 and event_count % 100 == 0:
        return min(5, event_count // 20)
    return 0


def clamp_score(score: int) -> int:
    result = score
    if result < REPUTATION_MIN:
        result = REPUTATION_MIN
    if result > REPUTATION_MAX:
        result = REPUTATION_MAX
    return int(result)
