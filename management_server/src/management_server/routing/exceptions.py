"""
Routing exceptions — typed error hierarchy for the Routing Engine.
"""

from __future__ import annotations


class RoutingError(Exception):
    """Base exception for all routing-related errors."""


class RuleNotFoundError(RoutingError):
    """Routing rule not found."""

    def __init__(self, rule_id: str) -> None:
        self.rule_id = rule_id
        super().__init__(f"Routing rule not found: {rule_id}")


class InvalidDestinationError(RoutingError):
    """Unknown or invalid destination."""

    def __init__(self, destination: str) -> None:
        self.destination = destination
        super().__init__(f"Invalid destination: {destination}")


class InvalidPriorityError(RoutingError):
    """Invalid priority level."""

    def __init__(self, priority: str) -> None:
        self.priority = priority
        super().__init__(f"Invalid priority: {priority}")


class InvalidTemplateError(RoutingError):
    """Invalid template reference."""

    def __init__(self, template: str) -> None:
        self.template = template
        super().__init__(f"Invalid template: {template}")


class RoutingValidationError(RoutingError):
    """Routing configuration validation failure."""


class RoutingLoadError(RoutingError):
    """Routing YAML loading failure."""


class RoutingRepositoryError(RoutingError):
    """Database error during routing operations."""


class NoMatchingRuleError(RoutingError):
    """No routing rule matched the event."""
