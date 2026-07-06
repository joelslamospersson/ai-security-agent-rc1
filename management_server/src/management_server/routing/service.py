"""
Routing service — orchestrates loading, evaluation, and storage of routing decisions.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog

from management_server.routing.evaluator import RoutingEvaluator
from management_server.routing.loader import RoutingLoader
from management_server.routing.matcher import RoutingMatcher
from management_server.routing.metrics import RoutingMetricsCollector
from management_server.routing.models import RoutingDecision, RoutingRule
from management_server.routing.repository import RoutingRepository
from management_server.routing.schemas import (
    EventToRoute,
    RoutingConfigReloadResponse,
    RoutingDecisionSchema,
    RoutingEvaluateResponse,
    RoutingRuleSchema,
)
from management_server.routing.validator import RoutingValidator

logger = structlog.get_logger("routing.service")


class RoutingService:
    """Routing Engine service.

    Loads routing config, evaluates events, produces immutable decisions.
    """

    def __init__(
        self,
        repository: RoutingRepository,
        loader: RoutingLoader | None = None,
        matcher: RoutingMatcher | None = None,
        metrics: RoutingMetricsCollector | None = None,
    ) -> None:
        self._repository = repository
        self._loader = loader or RoutingLoader()
        self._matcher = matcher or RoutingMatcher([])
        self._evaluator = RoutingEvaluator(self._matcher)
        self._metrics = metrics or RoutingMetricsCollector()
        self._rules_loaded = False

    async def load_config(self) -> RoutingConfigReloadResponse:
        """Load routing configuration from YAML files."""
        rules, profiles = self._loader.load_all()
        errors: list[str] = []

        if not rules:
            return RoutingConfigReloadResponse(
                rules_loaded=0,
                profiles_loaded=0,
                errors=["No routing rules found in config"],
            )

        # Validate
        validation_errors = RoutingValidator.validate_all(rules)
        if validation_errors:
            for err in validation_errors:
                self._metrics.validation_failure()
                logger.error("Routing validation error", error=err)
            errors.extend(validation_errors)

        # Load valid rules
        valid_rules: list[RoutingRule] = []
        for rule in rules:
            validator = RoutingValidator(valid_rules)
            rule_errors = validator.validate_rule(rule)
            if not rule_errors:
                valid_rules.append(rule)
                await self._repository.save_rule(rule)
            else:
                for e in rule_errors:
                    self._metrics.validation_failure()
                    logger.error("Invalid rule", rule=rule.name, error=e)
                    errors.append(f"[{rule.name}] {e}")

        self._matcher.set_rules(valid_rules)
        self._rules_loaded = True

        logger.info(
            "Routing config loaded",
            rules=len(valid_rules),
            profiles=len(profiles),
            errors=len(errors),
        )

        return RoutingConfigReloadResponse(
            rules_loaded=len(valid_rules),
            profiles_loaded=len(profiles),
            errors=errors,
        )

    async def evaluate(self, event: EventToRoute) -> RoutingEvaluateResponse:
        """Evaluate an event against routing rules."""
        start = datetime.now(tz=UTC)

        decision = self._evaluator.evaluate(
            machine_id=event.machine_id,
            event_type=event.event_type,
            machine_policy=event.policy,
            machine_state=event.machine_state,
            severity=event.severity,
            feature_flags=event.feature_flags,
            capabilities=event.capabilities,
            environment=event.environment,
            metadata=event.metadata,
        )

        # Persist decision
        await self._repository.save_decision(decision)

        elapsed = (datetime.now(tz=UTC) - start).total_seconds() * 1000
        self._metrics.decision_created(elapsed)

        if decision.matched_rule and decision.matched_rule != "__default__":
            self._metrics.rule_matched()
        else:
            self._metrics.default_route_used()

        return RoutingEvaluateResponse(
            decision=self._decision_to_schema(decision),
            matched=decision.matched_rule != "__default__",
        )

    async def get_decision(self, decision_id: str) -> RoutingDecisionSchema | None:
        """Get a routing decision by ID."""
        import json

        record = await self._repository.get_decision(decision_id)
        if record is None:
            return None
        dests = record.get("destinations", [])
        if isinstance(dests, str):
            try:
                dests = json.loads(dests)
            except (json.JSONDecodeError, TypeError):
                dests = []
        return RoutingDecisionSchema(
            decision_id=record.get("decision_id", ""),
            machine_id=record.get("machine_id", ""),
            event_type=record.get("event_type", ""),
            destinations=dests,
            priority=record.get("priority", "normal"),
            template=record.get("template", "detailed"),
            rate_limit_profile=record.get("rate_limit_profile", "normal"),
            retention_policy=record.get("retention_policy", "standard"),
            matched_rule=record.get("matched_rule", ""),
        )

    async def list_decisions(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """List routing decisions with pagination."""
        records, total = await self._repository.list_decisions(limit, offset)
        decisions = []
        for r in records:
            dests = r.get("destinations", [])
            if isinstance(dests, str):
                try:
                    dests = json.loads(dests)
                except (json.JSONDecodeError, TypeError):
                    dests = []
            decisions.append(
                RoutingDecisionSchema(
                    decision_id=r.get("decision_id", ""),
                    machine_id=r.get("machine_id", ""),
                    event_type=r.get("event_type", ""),
                    destinations=dests,
                    priority=r.get("priority", "normal"),
                    template=r.get("template", "detailed"),
                    matched_rule=r.get("matched_rule", ""),
                )
            )
        return {"decisions": decisions, "total": total}

    async def list_rules(self) -> list[RoutingRuleSchema]:
        """List all loaded routing rules."""
        records = await self._repository.list_rules()
        schemas: list[RoutingRuleSchema] = []
        for r in records:
            et = r.get("event_types", ["*"])
            if isinstance(et, str):
                try:
                    et = json.loads(et)
                except (json.JSONDecodeError, TypeError):
                    et = ["*"]
            dests = r.get("destinations", [])
            if isinstance(dests, str):
                try:
                    dests = json.loads(dests)
                except (json.JSONDecodeError, TypeError):
                    dests = []
            schemas.append(
                RoutingRuleSchema(
                    name=r.get("name", ""),
                    description=r.get("description", ""),
                    event_types=et,
                    destinations=dests,
                    priority=r.get("priority", "normal"),
                    template=r.get("template", "detailed"),
                    enabled=r.get("enabled", True),
                )
            )
        return schemas

    async def get_metrics(self) -> dict[str, int | float]:
        """Get routing metrics."""
        dec_count = await self._repository.get_decision_count()
        rule_count = await self._repository.get_rule_count()
        snap = self._metrics.snapshot()
        return {
            "routing_decisions": dec_count,
            "rule_matches": snap.rule_matches,
            "default_route_usage": snap.default_route_usage,
            "validation_failures": snap.validation_failures,
            "evaluation_latency_ms": snap.evaluation_latency_ms,
            "loaded_rules": rule_count,
        }

    @staticmethod
    def _decision_to_schema(decision: RoutingDecision) -> RoutingDecisionSchema:
        return RoutingDecisionSchema(
            decision_id=decision.decision_id,
            timestamp=decision.timestamp,
            machine_id=decision.machine_id,
            event_type=decision.event_type,
            destinations=list(decision.destinations),
            priority=decision.priority.value,
            template=decision.template.value,
            rate_limit_profile=decision.rate_limit_profile,
            retention_policy=decision.retention_policy,
            matched_rule=decision.matched_rule,
            metadata=dict(decision.metadata),
        )
