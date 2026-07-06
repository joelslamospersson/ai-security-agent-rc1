"""
Rule Engine — evaluates normalized events against declarative rules.

The Rule Engine is generic. It knows nothing about specific threat types.
It evaluates conditions, produces RuleMatches, and never enforces bans.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from security_agent.rules.compiler import compile_rules
from security_agent.rules.context import RuleContext
from security_agent.rules.matcher import evaluate_condition
from security_agent.rules.metrics import RuleMetricsCollector, RuleMetricsSnapshot
from security_agent.rules.models import Rule, RuleMatch

logger = logging.getLogger("rules.engine")

MAX_RULES = 10000


class RuleEngine:
    """Evaluates rules against events.

    Usage:
        engine = RuleEngine()
        engine.load_rules(rules_list)
        matches = engine.evaluate(event_dict, context)
    """

    def __init__(self) -> None:
        self._rules: list[Rule] = []
        self._compiled: dict[str, dict[str, Any]] = {}
        self._metrics = RuleMetricsCollector()
        self._enabled_rules: set[str] = set()

    def load_rules(self, rules: list[Rule]) -> None:
        """Load and compile rules."""
        if len(self._rules) + len(rules) > MAX_RULES:
            logger.warning(
                "Approaching rule limit",
                extra={
                    "current": len(self._rules),
                    "new": len(rules),
                    "max": MAX_RULES,
                },
            )

        self._rules.extend(rules)
        compiled = compile_rules(rules)
        self._compiled.update(compiled)
        self._metrics.rules_loaded(len(rules))

        for rule in rules:
            if rule.enabled:
                self._enabled_rules.add(rule.id)

        logger.info(
            "Rules loaded",
            extra={"total": len(self._rules), "enabled": len(self._enabled_rules)},
        )

    def enable_rule(self, rule_id: str) -> None:
        """Enable a rule by ID."""
        for rule in self._rules:
            if rule.id == rule_id:
                self._enabled_rules.add(rule_id)
                return

    def disable_rule(self, rule_id: str) -> None:
        """Disable a rule by ID."""
        self._enabled_rules.discard(rule_id)

    def is_enabled(self, rule_id: str) -> bool:
        return rule_id in self._enabled_rules

    def evaluate(
        self,
        event: dict[str, Any],
        context: RuleContext | None = None,
    ) -> list[RuleMatch]:
        """Evaluate an event against all enabled rules.

        Args:
            event: Event as flat dict (from normalized event).
            context: Optional evaluation context.

        Returns:
            List of RuleMatches (empty if no rules matched).
        """
        matches: list[RuleMatch] = []

        for rule in self._rules:
            if rule.id not in self._enabled_rules:
                continue

            start = time.monotonic()

            try:
                rule_matched = evaluate_condition(
                    rule.conditions,
                    event,
                    compiled_patterns=self._compiled.get(rule.id, {}).get("patterns"),
                )
            except Exception as e:
                self._metrics.evaluation_error()
                logger.error(
                    "Rule evaluation error",
                    extra={"rule_id": rule.id, "error": str(e)},
                )
                continue

            elapsed = time.monotonic() - start
            self._metrics.record_latency(elapsed)
            self._metrics.rule_evaluated()

            if rule_matched:
                self._metrics.rule_matched()
                matches.append(
                    RuleMatch(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        event_id=event.get("event_id", ""),
                        correlation_id=context.correlation_id if context else "",
                        confidence=rule.confidence,
                        severity=rule.severity,
                        threat_score=rule.threat_score,
                        evidence=f"Matched rule: {rule.name} ({rule.id})",
                    )
                )

            if elapsed > 0.1:
                logger.warning(
                    "Slow rule evaluation",
                    extra={"rule_id": rule.id, "latency_ms": round(elapsed * 1000)},
                )

        return matches

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @property
    def enabled_count(self) -> int:
        return len(self._enabled_rules)

    def get_rule(self, rule_id: str) -> Rule | None:
        for rule in self._rules:
            if rule.id == rule_id:
                return rule
        return None

    def metrics_snapshot(self) -> RuleMetricsSnapshot:
        return self._metrics.snapshot()

    def clear(self) -> None:
        self._rules.clear()
        self._compiled.clear()
        self._enabled_rules.clear()
