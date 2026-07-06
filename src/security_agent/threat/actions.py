"""
Action recommendation utilities.

Recommendations are informational only.
They are never executed by the Threat Engine.
"""

from __future__ import annotations

from security_agent.threat.models import RecommendedAction


def action_name(action: RecommendedAction) -> str:
    """Return human-readable name for a recommended action."""
    names = {
        RecommendedAction.IGNORE: "Ignore",
        RecommendedAction.MONITOR: "Monitor",
        RecommendedAction.INCREASE_REPUTATION: "Increase Reputation",
        RecommendedAction.TEMPORARY_BAN: "Temporary Ban",
        RecommendedAction.PERMANENT_BAN: "Permanent Ban",
        RecommendedAction.NOTIFY_ADMIN: "Notify Administrator",
    }
    return names.get(action, "Unknown")


def action_requires_attention(action: RecommendedAction) -> bool:
    """Check if an action requires human attention."""
    return action in (
        RecommendedAction.TEMPORARY_BAN,
        RecommendedAction.PERMANENT_BAN,
        RecommendedAction.NOTIFY_ADMIN,
    )
