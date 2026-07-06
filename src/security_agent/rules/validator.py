"""
Rule validator — validates raw rule dicts before Rule object creation.

Checks:
- Required fields present
- Valid enum values for operators
- Valid severity/confidence/threat_score ranges
- No duplicate rule IDs
"""

from __future__ import annotations

from typing import Any

from security_agent.rules.models import ConditionOp, LogicalOp


def validate_rules(rule_dicts: list[dict[str, Any]]) -> list[str]:
    """Validate a list of raw rule dicts. Returns list of error messages.

    Empty list means all rules are valid.
    The caller should refuse to start if any errors are found.
    """
    errors: list[str] = []
    seen_ids: set[str] = set()

    for rule in rule_dicts:
        rule_id = rule.get("id", "")
        rule_name = rule.get("name", "")

        if not rule_id:
            errors.append("Rule: id is required")
        else:
            if rule_id in seen_ids:
                errors.append(f"Duplicate rule ID: {rule_id}")
            seen_ids.add(rule_id)

        if not rule_name:
            errors.append(f"Rule '{rule_id}': name is required")

        # Range checks
        severity = rule.get("severity", 0)
        if not (0 <= severity <= 10):
            errors.append(f"Rule '{rule_id}': severity must be 0-10")
        confidence = rule.get("confidence", 0)
        if not (0 <= confidence <= 100):
            errors.append(f"Rule '{rule_id}': confidence must be 0-100")
        threat_score = rule.get("threat_score", 0)
        if not (0 <= threat_score <= 100):
            errors.append(f"Rule '{rule_id}': threat_score must be 0-100")

        # Validate conditions
        conditions = rule.get("conditions", {})
        if not conditions:
            errors.append(f"Rule '{rule_id}': no conditions defined")

        errors.extend(_validate_conditions(conditions, rule_id))

    return errors


def _validate_conditions(
    condition: dict[str, Any],
    rule_id: str,
    path: str = "root",
) -> list[str]:
    """Recursively validate conditions from raw dict."""
    errors: list[str] = []

    if not isinstance(condition, dict):
        return errors

    logical = condition.get("logical")
    if logical:
        valid_logical = {op.value for op in LogicalOp}
        if logical not in valid_logical:
            errors.append(
                f"Rule '{rule_id}': invalid logical operator '{logical}' at {path}"
            )
        sub_conditions = condition.get("conditions", [])
        if not sub_conditions:
            errors.append(
                f"Rule '{rule_id}': logical '{logical}' without conditions at {path}"
            )
        for i, sub in enumerate(sub_conditions):
            errors.extend(_validate_conditions(sub, rule_id, f"{path}[{i}]"))
        return errors

    field = condition.get("field", "")
    operator = condition.get("operator", "")
    if not field and not operator:
        errors.append(
            f"Rule '{rule_id}': condition at {path} must have 'field' or 'logical'"
        )
        return errors

    if operator:
        valid_ops = {op.value for op in ConditionOp}
        if operator not in valid_ops:
            errors.append(f"Rule '{rule_id}': invalid operator '{operator}' at {path}")

    return errors
