"""
Correlation matcher — determines correlation key values from RuleMatches.
"""

from __future__ import annotations

from typing import Any

from security_agent.correlation.models import CorrelationKey


def extract_key_value(
    key: CorrelationKey,
    rule_match: Any,
    event: dict[str, Any] | None = None,
) -> str:
    """Extract a correlation key value from a RuleMatch and optional event data.

    Args:
        key: The correlation key type to extract.
        rule_match: A RuleMatch object.
        event: Optional event dict with additional fields.

    Returns:
        String value of the correlation key, or "unknown" if not found.
    """
    if key == CorrelationKey.CORRELATION_ID:
        val = getattr(rule_match, "correlation_id", None) or ""
        return val if val else "unknown"

    if event is not None:
        if key == CorrelationKey.SOURCE_IP:
            return event.get("source_ip") or event.get("ip") or "unknown"
        if key == CorrelationKey.DEST_IP:
            return event.get("dest_ip") or "unknown"
        if key == CorrelationKey.USERNAME:
            return event.get("username") or event.get("user") or "unknown"
        if key == CorrelationKey.HOSTNAME:
            return event.get("hostname") or "unknown"
        if key == CorrelationKey.PROCESS:
            return event.get("process") or event.get("exe") or "unknown"
        if key == CorrelationKey.SESSION:
            return event.get("session") or event.get("session_id") or "unknown"
        if key == CorrelationKey.CONTAINER_ID:
            return event.get("container_id") or event.get("container") or "unknown"

    return "unknown"
