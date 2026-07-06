"""
Attack chain loader — loads YAML chain definitions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from security_agent.correlation.exceptions import ChainLoadError, ChainValidationError
from security_agent.correlation.models import (
    AttackChain,
    ChainStage,
    CorrelationKey,
    StageType,
)
from security_agent.correlation.validator import validate_chains


def load_chains(path: str | Path) -> list[AttackChain]:
    """Load attack chains from a YAML file.

    Args:
        path: Path to YAML chain file.

    Returns:
        List of AttackChain objects.

    Raises:
        ChainLoadError: File cannot be read or parsed.
        ChainValidationError: Chains fail validation.
    """
    path = Path(path)
    if not path.exists():
        raise ChainLoadError(f"Chain file not found: {path}")

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ChainLoadError(f"Malformed YAML in {path}: {e}") from e

    if data is None:
        return []

    chain_dicts = data if isinstance(data, list) else data.get("chains", [])

    errors = validate_chains(chain_dicts)
    if errors:
        raise ChainValidationError(
            f"Chain validation failed for {path}:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    return [_dict_to_chain(d) for d in chain_dicts]


def _dict_to_chain(d: dict[str, Any]) -> AttackChain:
    """Convert a raw chain dict to an AttackChain object."""
    stages = []
    for s in d.get("stages", []):
        stages.append(
            ChainStage(
                stage_id=s.get("stage_id", ""),
                stage_type=StageType(s.get("stage_type", "ordered")),
                rule_ids=tuple(s.get("rule_ids", [])),
                timeout=s.get("timeout", 300),
                confidence_modifier=s.get("confidence_modifier", 0),
                description=s.get("description", ""),
            )
        )

    return AttackChain(
        id=d.get("id", ""),
        name=d.get("name", ""),
        description=d.get("description", ""),
        version=d.get("version", "1.0"),
        enabled=d.get("enabled", True),
        correlation_key=CorrelationKey(d.get("correlation_key", "source_ip")),
        timeout=d.get("timeout", 3600),
        stages=tuple(stages),
        confidence_modifier=d.get("confidence_modifier", 0),
        severity=d.get("severity", 0),
        threat_score=d.get("threat_score", 0),
    )
