"""
Rule loader — loads YAML rule files and converts them to Rule objects.

Flow:
1. Read YAML file
2. Parse YAML → list of dicts
3. Validate dicts
4. Convert dicts → Rule objects
5. Compile Rule objects → compiled patterns
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from security_agent.rules.compiler import compile_rules
from security_agent.rules.exceptions import RuleLoadError, RuleValidationError
from security_agent.rules.models import Condition, ConditionOp, LogicalOp, Rule
from security_agent.rules.validator import validate_rules


def load_rules(path: str | Path) -> list[Rule]:
    """Load rules from a YAML file.

    Args:
        path: Path to YAML rule file.

    Returns:
        List of compiled Rule objects.

    Raises:
        RuleLoadError: File cannot be read or parsed.
        RuleValidationError: Rules fail validation.
    """
    path = Path(path)

    if not path.exists():
        raise RuleLoadError(f"Rule file not found: {path}")

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise RuleLoadError(f"Malformed YAML in {path}: {e}") from e

    if data is None:
        return []

    rule_dicts = data if isinstance(data, list) else data.get("rules", [])

    # Validate
    errors = validate_rules(rule_dicts)
    if errors:
        raise RuleValidationError(
            f"Rule validation failed for {path}:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    # Convert to Rule objects
    rules = [_dict_to_rule(d) for d in rule_dicts]

    # Compile
    compile_rules(rules)

    return rules


def _dict_to_condition(d: dict[str, Any]) -> Condition:
    """Convert a raw condition dict to a Condition object."""
    logical = d.get("logical")
    if logical:
        children = tuple(_dict_to_condition(c) for c in d.get("conditions", []))
        return Condition(logical=LogicalOp(logical), conditions=children)

    operator = d.get("operator")
    return Condition(
        field=d.get("field", ""),
        operator=ConditionOp(operator) if operator else None,
        value=d.get("value"),
    )


def _dict_to_rule(d: dict[str, Any]) -> Rule:
    """Convert a raw rule dict to a Rule object."""
    return Rule(
        id=d.get("id", ""),
        name=d.get("name", ""),
        description=d.get("description", ""),
        enabled=d.get("enabled", True),
        version=d.get("version", "1.0"),
        author=d.get("author", ""),
        category=d.get("category", ""),
        severity=d.get("severity", 0),
        confidence=d.get("confidence", 0),
        threat_score=d.get("threat_score", 0),
        conditions=_dict_to_condition(d.get("conditions", {})),
        ban_duration=d.get("ban_duration", 0),
        alert_channel=d.get("alert_channel", ""),
    )
