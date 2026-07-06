"""Rule Engine exceptions."""

from __future__ import annotations


class RuleError(Exception):
    """Base exception for Rule Engine errors."""


class RuleLoadError(RuleError):
    """Raised when a rule file cannot be loaded."""


class RuleValidationError(RuleError):
    """Raised when a rule fails validation."""


class RuleCompilationError(RuleError):
    """Raised when a rule cannot be compiled."""


class RuleExecutionError(RuleError):
    """Raised when a rule fails during evaluation."""


class RuleNotFoundError(RuleError):
    """Raised when a rule ID is not found."""


class DuplicateRuleError(RuleError):
    """Raised when a rule with duplicate ID is registered."""
