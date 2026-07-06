"""
Routing validator — validates routing rule configurations.
"""

from __future__ import annotations

import structlog

from management_server.routing.models import RoutingRule

logger = structlog.get_logger("routing.validator")

VALID_EVENT_TYPES: set[str] = {
    "heartbeat",
    "critical_alert",
    "warning",
    "machine_online",
    "machine_offline",
    "registration",
    "policy_change",
    "certificate_expiring",
    "audit_event",
    "*",
}

KNOWN_DESTINATIONS = {
    "discord",
    "email",
    "webhook",
    "syslog",
    "dashboard",
    "archive",
    "console",
    "none",
}

KNOWN_TEMPLATES = {"minimal", "detailed", "discord_embed", "markdown", "json"}

KNOWN_PRIORITIES = {"immediate", "high", "normal", "low", "bulk"}


class RoutingValidator:
    """Validates routing rules and configurations."""

    def __init__(self, known_rules: list[RoutingRule] | None = None) -> None:
        self._known_names: set[str] = {r.name for r in (known_rules or [])}

    def validate_rule(self, rule: RoutingRule) -> list[str]:
        """Validate a single routing rule. Returns list of error messages."""
        errors: list[str] = []

        if not rule.name:
            errors.append("Rule name is required")

        if rule.name in self._known_names:
            errors.append(f"Duplicate rule name: '{rule.name}'")

        # Validate event types
        for et in rule.event_types:
            if et not in VALID_EVENT_TYPES and not et.startswith("*"):
                errors.append(f"Unknown event type: '{et}'")

        # Validate destinations
        for d in rule.destinations:
            if d.lower() not in KNOWN_DESTINATIONS:
                errors.append(f"Unknown destination: '{d}'")

        # Validate priority
        if rule.priority.value not in KNOWN_PRIORITIES:
            errors.append(f"Invalid priority: '{rule.priority.value}'")

        # Validate template
        if rule.template.value.lower() not in KNOWN_TEMPLATES:
            errors.append(f"Invalid template: '{rule.template.value}'")

        return errors

    def validate_rules(self, rules: list[RoutingRule]) -> list[list[str]]:
        """Validate multiple rules. Returns list of error lists."""
        return [self.validate_rule(r) for r in rules]

    @staticmethod
    def validate_all(rules: list[RoutingRule]) -> list[str]:
        """Validate all rules and return flat error list."""
        validator = RoutingValidator()
        all_errors: list[str] = []
        for rule in rules:
            name = rule.name or "unnamed"
            errors = validator.validate_rule(rule)
            for e in errors:
                all_errors.append(f"[{name}] {e}")
            validator._known_names.add(rule.name)
        return all_errors

    @staticmethod
    def validate_yaml_string(yaml_string: str) -> list[str]:
        """Validate a YAML routing configuration string."""
        from management_server.routing.loader import RoutingLoader

        try:
            loader = RoutingLoader()
            rules, _profiles = loader.load_yaml_string(yaml_string)
        except Exception as e:
            return [f"YAML load error: {e}"]
        return RoutingValidator.validate_all(rules)
