"""
Routing evaluator — evaluates an event against rules and produces a decision.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from management_server.routing.decision import RoutingDecisionFactory
from management_server.routing.matcher import RoutingMatcher
from management_server.routing.models import (
    Priority,
    RoutingDecision,
    RoutingRule,
    Template,
)

logger = structlog.get_logger("routing.evaluator")


class RoutingEvaluator:
    """Evaluates events against routing rules to produce RoutingDecisions.

    Pipeline:
        1. Event arrives with context
        2. Match against enabled rules
        3. If match found → produce decision from matched rule
        4. If no match → produce default decision
    """

    def __init__(self, matcher: RoutingMatcher) -> None:
        self._matcher = matcher

    def evaluate(
        self,
        machine_id: str,
        event_type: str,
        machine_policy: str = "default",
        machine_state: str = "healthy",
        severity: str = "info",
        feature_flags: dict[str, bool] | None = None,
        capabilities: list[str] | None = None,
        environment: str = "production",
        metadata: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Evaluate an event and produce a routing decision."""
        start = datetime.now(tz=UTC)

        matched_rule = self._matcher.match_first(
            event_type=event_type,
            machine_policy=machine_policy,
            machine_state=machine_state,
            severity=severity,
            feature_flags=feature_flags,
            capabilities=capabilities,
            environment=environment,
        )

        if matched_rule:
            decision = self._from_rule(matched_rule, machine_id, event_type, metadata)
            elapsed = (datetime.now(tz=UTC) - start).total_seconds() * 1000
            logger.info(
                "Routing decision from rule",
                machine_id=machine_id,
                event_type=event_type,
                rule=matched_rule.name,
                latency_ms=round(elapsed, 2),
            )
        else:
            decision = self._default_decision(machine_id, event_type, metadata)
            logger.info(
                "Routing decision from default",
                machine_id=machine_id,
                event_type=event_type,
            )

        return decision

    def evaluate_bulk(
        self,
        events: list[dict[str, Any]],
    ) -> list[RoutingDecision]:
        """Evaluate multiple events."""
        return [self.evaluate(**event) for event in events]

    def _from_rule(
        self,
        rule: RoutingRule,
        machine_id: str,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Create a decision from a matched rule."""
        return RoutingDecisionFactory.create(
            machine_id=machine_id,
            event_type=event_type,
            destinations=rule.destinations,
            priority=rule.priority,
            template=rule.template,
            rate_limit_profile=rule.rate_limit_profile,
            retention_policy=rule.retention_policy,
            matched_rule=rule.name,
            metadata=metadata,
        )

    @staticmethod
    def _default_decision(
        machine_id: str,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Create a default routing decision when no rule matches."""
        return RoutingDecisionFactory.create(
            machine_id=machine_id,
            event_type=event_type,
            destinations=["console"],
            priority=Priority.LOW,
            template=Template.MINIMAL,
            rate_limit_profile="low",
            matched_rule="__default__",
            metadata=metadata,
        )
