"""
Condition matcher — evaluates conditions against an event dict.
"""

from __future__ import annotations

import re
from typing import Any

from security_agent.rules.models import Condition, ConditionOp, LogicalOp


def _get_field(event: dict[str, Any], field_path: str) -> Any:
    parts = field_path.split(".")
    current: Any = event
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None
    return current


def _compare(value: Any, expected: Any) -> bool:
    if isinstance(expected, str) and isinstance(value, str):
        return value == expected
    if isinstance(expected, (int, float)):
        try:
            return bool(float(value) == float(expected)) if value is not None else False
        except (ValueError, TypeError):
            return False
    return bool(value == expected)


def evaluate_condition(
    condition: Condition,
    event: dict[str, Any],
    compiled_patterns: dict[str, Any] | None = None,
) -> bool:
    if condition.logical == LogicalOp.AND:
        return all(
            evaluate_condition(c, event, compiled_patterns)
            for c in condition.conditions
        )

    if condition.logical == LogicalOp.OR:
        return any(
            evaluate_condition(c, event, compiled_patterns)
            for c in condition.conditions
        )

    if condition.logical == LogicalOp.NOT:
        return not any(
            evaluate_condition(c, event, compiled_patterns)
            for c in condition.conditions
        )

    field_val = _get_field(event, condition.field)

    if condition.operator == ConditionOp.EXISTS:
        return field_val is not None
    if condition.operator == ConditionOp.MISSING:
        return field_val is None
    if field_val is None:
        return False

    str_val = str(field_val) if not isinstance(field_val, str) else field_val
    expected = condition.value

    if condition.operator == ConditionOp.EQUALS:
        return _compare(field_val, expected)
    if condition.operator == ConditionOp.NOT_EQUALS:
        return not _compare(field_val, expected)
    if condition.operator == ConditionOp.CONTAINS:
        return str(expected).lower() in str_val.lower()
    if condition.operator == ConditionOp.REGEX:
        if compiled_patterns and condition.field in compiled_patterns:
            pattern = compiled_patterns[condition.field]
        else:
            pattern = re.compile(str(expected))
        return bool(pattern.search(str_val))
    if condition.operator == ConditionOp.STARTS_WITH:
        return str_val.startswith(str(expected))
    if condition.operator == ConditionOp.ENDS_WITH:
        return str_val.endswith(str(expected))
    if condition.operator == ConditionOp.GT:
        return _numeric_cmp(str_val, expected, lambda a, b: a > b)
    if condition.operator == ConditionOp.GTE:
        return _numeric_cmp(str_val, expected, lambda a, b: a >= b)
    if condition.operator == ConditionOp.LT:
        return _numeric_cmp(str_val, expected, lambda a, b: a < b)
    if condition.operator == ConditionOp.LTE:
        return _numeric_cmp(str_val, expected, lambda a, b: a <= b)

    return False


def _numeric_cmp(str_val: str, expected: Any, op: Any) -> bool:
    try:
        return bool(op(float(str_val), float(expected)))
    except (ValueError, TypeError):
        return False
