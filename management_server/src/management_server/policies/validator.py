"""
Policy validator — validates policy names, inheritance, types, ranges, and feature flags.
"""

from __future__ import annotations

import re

import structlog

from management_server.policies.models import Policy
from management_server.policies.schemas import PolicyValidateResponse

logger = structlog.get_logger("policies.validator")

VALID_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

ALLOWED_PROTOCOL_VERSIONS = {"1.0"}
KNOWN_PROPERTIES = {
    "description",
    "version",
    "parent",
    "heartbeat_interval_seconds",
    "notification_retention_days",
    "log_retention_days",
    "ip_masking_enabled",
    "maintenance_mode",
    "allowed_protocol_versions",
    "feature_flags",
}

KNOWN_FEATURE_FLAGS = {
    "discord",
    "geoip",
    "docker",
    "web_dashboard",
    "remote_commands",
    "experimental",
}

RANGE_CONSTRAINTS: dict[str, tuple[int, int]] = {
    "heartbeat_interval_seconds": (5, 3600),
    "notification_retention_days": (1, 365),
    "log_retention_days": (1, 3650),
}


class PolicyValidator:
    """Validates policies against structural and semantic rules."""

    def __init__(self, known_policies: list[Policy] | None = None) -> None:
        self._known_policies = {p.name: p for p in (known_policies or [])}

    def validate(self, policy: Policy) -> PolicyValidateResponse:
        """Validate a single policy. Returns validation result."""
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Name validation
        if not policy.name:
            errors.append("Policy name is required")
        elif not VALID_NAME_RE.match(policy.name):
            errors.append(f"Invalid policy name '{policy.name}': must match [a-z][a-z0-9_]*")

        # 2. Duplicate name check
        if policy.name in self._known_policies and self._known_policies[policy.name] is not policy:
            errors.append(f"Duplicate policy name: '{policy.name}'")

        # 3. Parent validation (basic; circular check is in inheritance.py)
        if policy.parent and policy.parent == policy.name:
            errors.append(f"Policy '{policy.name}' cannot be its own parent")
        if (
            policy.parent
            and policy.parent not in self._known_policies
            and policy.parent != policy.name
        ):
            warnings.append(f"Parent policy '{policy.parent}' not found (may be loaded later)")

        # 4. Unknown properties
        if policy.raw_yaml:
            for key in policy.raw_yaml:
                if key not in KNOWN_PROPERTIES and key != "name":
                    warnings.append(f"Unknown property: '{key}'")

        # 5. Range validation
        for field_name, (min_val, max_val) in RANGE_CONSTRAINTS.items():
            value = getattr(policy, field_name, None)
            if isinstance(value, (int, float)) and (value < min_val or value > max_val):
                errors.append(f"'{field_name}' = {value} out of range [{min_val}, {max_val}]")

        # 6. Protocol versions
        for pv in policy.allowed_protocol_versions:
            if pv not in ALLOWED_PROTOCOL_VERSIONS:
                warnings.append(f"Unsupported protocol version: '{pv}'")

        # 7. Feature flags validation
        if policy.raw_yaml and "feature_flags" in policy.raw_yaml:
            ff_data = policy.raw_yaml["feature_flags"]
            if isinstance(ff_data, dict):
                for key in ff_data:
                    if key not in KNOWN_FEATURE_FLAGS:
                        warnings.append(f"Unknown feature flag: '{key}'")
                    elif not isinstance(ff_data[key], bool):
                        errors.append(
                            f"Feature flag '{key}' must be boolean, got {type(ff_data[key]).__name__}"
                        )

        return PolicyValidateResponse(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_all(self, policies: list[Policy]) -> list[PolicyValidateResponse]:
        """Validate a list of policies."""
        return [self.validate(p) for p in policies]

    @staticmethod
    def validate_yaml_string(name: str, yaml_string: str) -> PolicyValidateResponse:
        """Validate a YAML string as a policy (for API validation endpoint)."""
        from management_server.policies.loader import PolicyLoader

        try:
            loader = PolicyLoader()
            policy = loader.load_yaml_string(name, yaml_string)
        except Exception as e:
            return PolicyValidateResponse(
                valid=False,
                errors=[str(e)],
            )
        validator = PolicyValidator()
        return validator.validate(policy)
