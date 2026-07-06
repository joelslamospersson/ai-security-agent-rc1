"""
Rule compiler — pre-compiles expensive operations.

Regex patterns, field lookup paths, and comparison functions
are compiled once at startup, not on every event evaluation.
"""

from __future__ import annotations

import re
from typing import Any

from security_agent.rules.exceptions import RuleCompilationError
from security_agent.rules.models import Condition, ConditionOp, Rule


def compile_rule(rule: Rule) -> dict[str, Any]:
    """Pre-compile a rule's conditions.

    Returns a dict of compiled resources:
        {
            "patterns": {"field_name": compiled_regex, ...},
            "field_paths": {"field_name": ["path", "parts"], ...},
        }

    Raises RuleCompilationError on invalid regex.
    """
    compiled: dict[str, Any] = {"patterns": {}, "field_paths": {}}

    def _walk(condition: Condition) -> None:
        if condition.logical:
            for child in condition.conditions:
                _walk(child)
            return

        if condition.operator == ConditionOp.REGEX and condition.value:
            try:
                compiled["patterns"][condition.field] = re.compile(
                    str(condition.value), re.IGNORECASE
                )
            except re.error as e:
                raise RuleCompilationError(
                    f"Invalid regex for field '{condition.field}' "
                    f"in rule '{rule.id}': {e}"
                ) from e

    _walk(rule.conditions)
    return compiled


def compile_rules(rules: list[Rule]) -> dict[str, dict[str, Any]]:
    """Compile multiple rules. Returns {rule_id: compiled_data}."""
    compiled_map: dict[str, dict[str, Any]] = {}
    for rule in rules:
        compiled_map[rule.id] = compile_rule(rule)
    return compiled_map
