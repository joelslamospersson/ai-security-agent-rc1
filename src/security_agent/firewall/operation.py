"""
Firewall operation factory — creates operations from BanDecisions.
"""

from __future__ import annotations

from security_agent.ban.models import BanAction, BanDecision
from security_agent.firewall.models import FirewallOperation, OperationType


def create_operation(decision: BanDecision) -> FirewallOperation | None:
    """Create a FirewallOperation from a BanDecision.

    Returns None if the decision requires no firewall action.
    """
    if decision.action == BanAction.WHITELIST_SKIP:
        return None
    if decision.action == BanAction.EXEMPTION_SKIP:
        return None
    if decision.action == BanAction.NO_ACTION:
        return None

    if decision.action == BanAction.WARNING:
        return FirewallOperation(
            correlation_id=decision.correlation_id,
            entity=decision.entity,
            entity_type=decision.entity_type,
            operation_type=OperationType.REFRESH,
            reason=decision.reason,
            evidence=decision.evidence,
        )

    if decision.action == BanAction.TEMPORARY_BAN:
        return FirewallOperation(
            correlation_id=decision.correlation_id,
            entity=decision.entity,
            entity_type=decision.entity_type,
            operation_type=OperationType.BAN,
            duration=decision.ban_duration,
            expires_at=_expires_at(decision.ban_duration),
            reason=decision.reason,
            evidence=decision.evidence,
        )

    if decision.action == BanAction.PERMANENT_BAN:
        return FirewallOperation(
            correlation_id=decision.correlation_id,
            entity=decision.entity,
            entity_type=decision.entity_type,
            operation_type=OperationType.BAN,
            duration=0,
            expires_at=0.0,
            reason=decision.reason,
            evidence=decision.evidence,
        )

    return None


def _expires_at(duration: int) -> float:
    if duration <= 0:
        return 0.0
    import time

    return time.time() + duration
