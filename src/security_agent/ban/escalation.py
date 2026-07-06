"""
Deterministic ban escalation.

Escalation must always be reproducible.
"""

from __future__ import annotations

from security_agent.ban.models import BAN_DURATIONS, BanLevel
from security_agent.ban.policy import PolicyConfig


def calculate_escalation(
    threat_score: int,
    confidence: int,
    previous_bans: int,
    reputation_score: int,
    is_repeat_offender: bool,
    is_whitelisted: bool,
    is_exempt: bool,
    policy: PolicyConfig,
) -> tuple[BanLevel, bool]:
    """Calculate escalation level.

    Args:
        threat_score: 0-100
        confidence: 0-100
        previous_bans: Number of prior bans for this entity
        reputation_score: Current reputation (-100 to 100)
        is_repeat_offender: Entity has been banned before
        is_whitelisted: Entity is whitelisted
        is_exempt: Entity is exempt
        policy: Current ban policy configuration

    Returns:
        (BanLevel, is_permanent) tuple.
    """
    if is_whitelisted or is_exempt:
        return BanLevel.WARNING, False

    if threat_score < policy.min_threat_score:
        return BanLevel.WARNING, False
    if confidence < policy.min_confidence:
        return BanLevel.WARNING, False

    if not policy.enable_temporary_bans:
        return BanLevel.WARNING, False

    # Calculate base level from threat score
    if threat_score >= 90:
        base = BanLevel.PERMANENT
    elif threat_score >= 80:
        base = BanLevel.BAN_7D
    elif threat_score >= 70:
        base = BanLevel.BAN_24H
    elif threat_score >= 60:
        base = BanLevel.BAN_3H
    elif threat_score >= 50:
        base = BanLevel.BAN_1H
    else:
        base = BanLevel.BAN_30M

    # Apply escalation rate from policy
    if policy.escalation_rate > 1.0:
        base = BanLevel(min(int(base) + int(previous_bans * 0.5), 7))
    elif previous_bans > 0:
        base = BanLevel(min(int(base) + previous_bans, 7))

    # Apply reputation penalty
    if reputation_score < -50:
        base = BanLevel(min(int(base) + 1, 7))

    # Cap at policy max
    base = BanLevel(min(int(base), policy.max_level))

    # Determine permanence
    is_permanent = base >= BanLevel.PERMANENT and policy.enable_permanent_bans

    if is_permanent:
        return base, True

    return base, False


def get_duration(level: BanLevel) -> int:
    """Get duration in seconds for a ban level."""
    return int(BAN_DURATIONS.get(level, 0))
