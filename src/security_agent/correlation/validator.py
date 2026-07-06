"""Attack chain validator — validates chain YAML before loading."""

from __future__ import annotations

from typing import Any

from security_agent.correlation.models import CorrelationKey, StageType


def validate_chains(chain_dicts: list[dict[str, Any]]) -> list[str]:
    """Validate a list of attack chain dicts. Returns error messages.

    Empty list means all chains are valid.
    """
    errors: list[str] = []
    seen_ids: set[str] = set()

    for chain in chain_dicts:
        cid = chain.get("id", "")
        if not cid:
            errors.append("Chain: id is required")
        else:
            if cid in seen_ids:
                errors.append(f"Duplicate chain ID: {cid}")
            seen_ids.add(cid)

        if not chain.get("name"):
            errors.append(f"Chain '{cid}': name is required")

        corr_key = chain.get("correlation_key", "")
        if corr_key:
            valid_keys = {k.value for k in CorrelationKey}
            if corr_key not in valid_keys:
                errors.append(f"Chain '{cid}': invalid correlation_key '{corr_key}'")

        stages = chain.get("stages", [])
        if not stages:
            errors.append(f"Chain '{cid}': no stages defined")
            continue

        seen_stages: set[str] = set()
        for i, stage in enumerate(stages):
            sid = stage.get("stage_id", f"stage_{i}")
            if sid in seen_stages:
                errors.append(f"Chain '{cid}': duplicate stage_id '{sid}'")
            seen_stages.add(sid)

            stype = stage.get("stage_type", "ordered")
            valid_types = {t.value for t in StageType}
            if stype not in valid_types:
                errors.append(f"Chain '{cid}': invalid stage_type '{stype}'")

            rule_ids = stage.get("rule_ids", [])
            if not rule_ids:
                errors.append(f"Chain '{cid}': stage '{sid}' has no rule_ids")

            timeout = stage.get("timeout", 300)
            if timeout < 1:
                errors.append(f"Chain '{cid}': stage '{sid}' timeout must be >= 1")

    return errors
