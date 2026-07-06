"""
Routing matcher — matches events against routing rules with wildcard support.
"""

from __future__ import annotations

from fnmatch import fnmatch

import structlog

from management_server.routing.models import RoutingRule

logger = structlog.get_logger("routing.matcher")


class RoutingMatcher:
    """Matches incoming events against routing rules.

    Supports:
        - Exact event type matching
        - Wildcard event type matching (fnmatch)
        - Policy matching
        - Machine state matching
        - Severity matching
        - Feature flag matching
        - Capability matching
        - Environment matching
    """

    def __init__(self, rules: list[RoutingRule] | None = None) -> None:
        self._rules = rules or []

    def set_rules(self, rules: list[RoutingRule]) -> None:
        self._rules = rules

    def match(
        self,
        event_type: str,
        machine_policy: str = "",
        machine_state: str = "",
        severity: str = "",
        feature_flags: dict[str, bool] | None = None,
        capabilities: list[str] | None = None,
        environment: str = "",
    ) -> list[RoutingRule]:
        """Find all routing rules that match the given event context.

        Rules are evaluated in order. All matching rules are returned.
        """
        matched: list[RoutingRule] = []

        for rule in self._rules:
            if not rule.enabled:
                continue

            if self._rule_matches(
                rule=rule,
                event_type=event_type,
                machine_policy=machine_policy,
                machine_state=machine_state,
                severity=severity,
                feature_flags=feature_flags,
                capabilities=capabilities,
                environment=environment,
            ):
                matched.append(rule)

        return matched

    def match_first(
        self,
        event_type: str,
        machine_policy: str = "",
        machine_state: str = "",
        severity: str = "",
        feature_flags: dict[str, bool] | None = None,
        capabilities: list[str] | None = None,
        environment: str = "",
    ) -> RoutingRule | None:
        """Find the first matching rule (highest priority match)."""
        for rule in self._rules:
            if not rule.enabled:
                continue
            if self._rule_matches(
                rule=rule,
                event_type=event_type,
                machine_policy=machine_policy,
                machine_state=machine_state,
                severity=severity,
                feature_flags=feature_flags,
                capabilities=capabilities,
                environment=environment,
            ):
                return rule
        return None

    def _rule_matches(
        self,
        rule: RoutingRule,
        event_type: str,
        machine_policy: str,
        machine_state: str,
        severity: str,
        feature_flags: dict[str, bool] | None,
        capabilities: list[str] | None,
        environment: str,
    ) -> bool:
        """Check if a single rule matches the event context."""
        # Event type — support wildcard
        if not self._match_field(event_type, rule.event_types):
            return False

        # Policy
        if rule.match_policy and not self._match_field(machine_policy, [rule.match_policy]):
            return False

        # Machine state
        if rule.match_machine_state and not self._match_field(
            machine_state, [rule.match_machine_state]
        ):
            return False

        # Severity
        if rule.match_severity and not self._match_field(severity, [rule.match_severity]):
            return False

        # Feature flags
        if rule.match_feature_flags:
            ff = feature_flags or {}
            for key, expected in rule.match_feature_flags.items():
                if ff.get(key) != expected:
                    return False

        # Capabilities
        if rule.match_capabilities:
            caps = capabilities or []
            for cap in rule.match_capabilities:
                if cap not in caps:
                    return False

        # Environment
        return not (
            rule.match_environment and not self._match_field(environment, [rule.match_environment])
        )

    @staticmethod
    def _match_field(value: str, patterns: list[str]) -> bool:
        """Match a value against a list of patterns (supports wildcard)."""
        if not patterns:
            return True
        for pattern in patterns:
            if pattern == "*" or value == pattern:
                return True
            if fnmatch(value, pattern):
                return True
        return False

    @property
    def rule_count(self) -> int:
        return len(self._rules)
