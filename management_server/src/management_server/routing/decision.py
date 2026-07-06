"""
Routing decision factory — creates immutable RoutingDecision instances.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from management_server.routing.models import Priority, RoutingDecision, Template


class RoutingDecisionFactory:
    """Factory for creating immutable RoutingDecision instances."""

    @staticmethod
    def create(
        machine_id: str,
        event_type: str,
        destinations: list[str],
        priority: Priority = Priority.NORMAL,
        template: Template = Template.DETAILED,
        rate_limit_profile: str = "normal",
        retention_policy: str = "standard",
        matched_rule: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Create a new immutable routing decision."""
        return RoutingDecision(
            decision_id=uuid4().hex[:16],
            machine_id=machine_id,
            event_type=event_type,
            destinations=list(destinations),
            priority=priority,
            template=template,
            rate_limit_profile=rate_limit_profile,
            retention_policy=retention_policy,
            matched_rule=matched_rule,
            metadata=metadata or {},
        )

    @staticmethod
    def from_dict(data: dict[str, Any]) -> RoutingDecision:
        """Create a decision from a dict (for deserialization)."""
        return RoutingDecision(
            decision_id=data.get("decision_id", ""),
            machine_id=data.get("machine_id", ""),
            event_type=data.get("event_type", ""),
            destinations=list(data.get("destinations", [])),
            priority=Priority.from_str(data.get("priority", "normal")),
            template=Template(str(data.get("template", "detailed")).lower()),
            rate_limit_profile=data.get("rate_limit_profile", "normal"),
            retention_policy=data.get("retention_policy", "standard"),
            matched_rule=data.get("matched_rule", ""),
            metadata=data.get("metadata", {}),
        )
