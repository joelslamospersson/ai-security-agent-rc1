"""
Ban decision logic — combines escalation, whitelist, exemption, policy.
"""

from __future__ import annotations

from security_agent.ban.escalation import calculate_escalation, get_duration
from security_agent.ban.history import BanHistory
from security_agent.ban.models import BanAction, BanDecision, BanLevel
from security_agent.ban.policy import get_policy


def make_decision(
    entity: str,
    entity_type: str,
    threat_score: int,
    confidence: int,
    reputation_score: int,
    correlation_id: str,
    history: BanHistory,
    policy_name: str = "balanced",
    whitelisted: bool = False,
    exempt: bool = False,
) -> BanDecision:
    """Make a ban decision based on all inputs.

    The decision is never enforced by this engine.
    """
    policy = get_policy(policy_name)
    record = history.lookup(entity, entity_type)

    previous_bans = record.total_bans if record else 0
    is_repeat = previous_bans > 0

    # Whitelist/exemption check
    if whitelisted:
        return BanDecision(
            entity=entity,
            entity_type=entity_type,
            threat_score=threat_score,
            confidence=confidence,
            reputation_score=reputation_score,
            correlation_id=correlation_id,
            action=BanAction.WHITELIST_SKIP,
            previous_ban_count=previous_bans,
            is_repeat_offender=is_repeat,
            reason=f"Entity '{entity}' is whitelisted",
            evidence="Whitelisted — no ban applied",
            policy_used=policy_name,
        )

    if exempt:
        return BanDecision(
            entity=entity,
            entity_type=entity_type,
            threat_score=threat_score,
            confidence=confidence,
            reputation_score=reputation_score,
            correlation_id=correlation_id,
            action=BanAction.EXEMPTION_SKIP,
            previous_ban_count=previous_bans,
            is_repeat_offender=is_repeat,
            reason=f"Entity '{entity}' is exempt",
            evidence="Exempt — no ban applied",
            policy_used=policy_name,
        )

    # Calculate escalation
    level, is_permanent = calculate_escalation(
        threat_score=threat_score,
        confidence=confidence,
        previous_bans=previous_bans,
        reputation_score=reputation_score,
        is_repeat_offender=is_repeat,
        is_whitelisted=False,
        is_exempt=False,
        policy=policy,
    )

    duration = get_duration(level)

    # Determine action type
    if level == BanLevel.WARNING and duration == 0:
        action = BanAction.WARNING
        reason = (
            f"Warning to '{entity}' (threat: {threat_score}, confidence: {confidence}%)"
        )
    elif is_permanent or level >= BanLevel.PERMANENT:
        action = BanAction.PERMANENT_BAN
        reason = f"Permanent ban for '{entity}' (repeat offender)"
    else:
        action = BanAction.TEMPORARY_BAN
        duration_str = _format_duration(duration)
        reason = f"Temporary ban for '{entity}' for {duration_str}"

    firewall_action = f"block_{entity_type}"
    if action == BanAction.WARNING:
        firewall_action = "none"
    elif action == BanAction.PERMANENT_BAN:
        firewall_action = f"block_{entity_type}_permanent"

    return BanDecision(
        entity=entity,
        entity_type=entity_type,
        threat_score=threat_score,
        confidence=confidence,
        reputation_score=reputation_score,
        correlation_id=correlation_id,
        action=action,
        escalation_level=level,
        ban_duration=duration,
        is_permanent=is_permanent,
        previous_ban_count=previous_bans,
        is_repeat_offender=is_repeat,
        reason=reason,
        evidence=f"Policy: {policy_name}, Level: {level.name}, Duration: {duration}s",
        recommended_firewall_action=firewall_action,
        policy_used=policy_name,
    )


def _format_duration(seconds: int) -> str:
    """Format seconds to human-readable duration."""
    if seconds >= 86400:
        return f"{seconds // 86400}d"
    if seconds >= 3600:
        return f"{seconds // 3600}h"
    if seconds >= 60:
        return f"{seconds // 60}m"
    return f"{seconds}s"
