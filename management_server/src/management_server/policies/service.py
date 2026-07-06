"""
Policy service — orchestrates policy loading, validation, inheritance, assignment, and overrides.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

import structlog

from management_server.policies.exceptions import (
    AssignmentError,
    InheritanceError,
    PolicyNotFoundError,
)
from management_server.policies.inheritance import PolicyInheritanceEngine
from management_server.policies.loader import PolicyLoader
from management_server.policies.metrics import PolicyMetricsCollector
from management_server.policies.models import Policy
from management_server.policies.repository import PolicyRepository
from management_server.policies.schemas import (
    FeatureFlagsSchema,
    PolicySchema,
    PolicyValidateResponse,
)
from management_server.policies.validator import PolicyValidator

logger = structlog.get_logger("policies.service")


class PolicyService:
    """Policy Engine service.

    Manages the full policy lifecycle: load, validate, inherit, assign, override.
    """

    def __init__(
        self,
        repository: PolicyRepository,
        loader: PolicyLoader | None = None,
        _validator: PolicyValidator | None = None,
        inheritance: PolicyInheritanceEngine | None = None,
        metrics: PolicyMetricsCollector | None = None,
    ) -> None:
        self._repository = repository
        self._loader = loader or PolicyLoader()
        self._inheritance = inheritance or PolicyInheritanceEngine()
        self._metrics = metrics or PolicyMetricsCollector()
        # Validator is created per-operation with current known policies

    async def load_policies(self) -> list[PolicySchema]:
        """Load all policies from YAML files, validate, and persist."""
        raw_policies = self._loader.load_all()

        if not raw_policies:
            logger.warning("No policy files found to load")
            return []

        # Validate
        validator = PolicyValidator(raw_policies)
        valid_policies: list[Policy] = []
        for policy in raw_policies:
            result = validator.validate(policy)
            if not result.valid:
                self._metrics.validation_failure()
                logger.error(
                    "Policy validation failed",
                    policy=policy.name,
                    errors=result.errors,
                )
                continue
            valid_policies.append(policy)

        # Register for inheritance
        self._inheritance.register_all(valid_policies)

        # Check for circular inheritance
        circular = self._inheritance.detect_circular()
        if circular:
            for name in circular:
                self._metrics.validation_failure()
                logger.error("Circular inheritance detected", policy=name)

        # Persist
        for policy in valid_policies:
            await self._repository.save_policy(policy)
            logger.info("Policy loaded", name=policy.name)

        self._metrics.reload()

        return [self._policy_to_schema(p) for p in valid_policies]

    async def get_policy(self, name: str) -> PolicySchema:
        """Get a single policy by name, with inheritance resolved."""
        try:
            resolved = self._inheritance.resolve(name)
            return self._policy_to_schema(resolved)
        except InheritanceError:
            pass

        # Fall back to raw from repository
        record = await self._repository.get_policy(name)
        policy = self._record_to_policy(record)
        return self._policy_to_schema(policy)

    async def list_policies(self) -> list[PolicySchema]:
        """List all stored policies."""
        records, _total = await self._repository.list_policies()
        schemas: list[PolicySchema] = []
        for record in records:
            try:
                resolved = self._inheritance.resolve(record["name"])
                schemas.append(self._policy_to_schema(resolved))
            except InheritanceError:
                policy = self._record_to_policy(record)
                schemas.append(self._policy_to_schema(policy))
        return schemas

    async def validate_policy_yaml(self, name: str, yaml_string: str) -> PolicyValidateResponse:
        """Validate a YAML policy string."""
        return PolicyValidator.validate_yaml_string(name, yaml_string)

    async def assign_policy(
        self,
        machine_uuid: str,
        policy_name: str,
        assigned_by: str = "system",
    ) -> dict[str, Any]:
        """Assign a policy to a machine."""
        # Verify policy exists
        if policy_name not in self._inheritance._policies:
            try:
                await self._repository.get_policy(policy_name)
            except Exception as e:
                raise PolicyNotFoundError(policy_name) from e

        result: dict[str, Any] = await self._repository.assign_policy(
            machine_uuid, policy_name, assigned_by
        )
        self._metrics.assignment()
        logger.info(
            "Policy assigned to machine",
            machine_uuid=machine_uuid,
            policy=policy_name,
            by=assigned_by,
        )
        return result

    async def set_override(
        self,
        machine_uuid: str,
        policy_name: str,
        key: str,
        value: object,
        created_by: str = "admin",
    ) -> dict[str, Any]:
        """Set a machine-specific policy override."""
        # Get current assignment to find original value
        assignment = await self._repository.get_assignment(machine_uuid)
        if assignment is None:
            raise AssignmentError(f"Machine {machine_uuid} has no policy assignment")

        try:
            policy = await self._repository.get_policy(policy_name)
        except Exception as e:
            raise PolicyNotFoundError(policy_name) from e

        original_value = str(policy.get(key, ""))

        result = await self._repository.set_override(
            machine_uuid=machine_uuid,
            policy_name=policy_name,
            key=key,
            value=str(value),
            original_value=original_value,
            created_by=created_by,
        )
        self._metrics.override()
        logger.info(
            "Policy override set",
            machine_uuid=machine_uuid,
            key=key,
            value=str(value),
        )
        return result  # type: ignore[no-any-return]

    async def get_assignment(self, machine_uuid: str) -> dict[str, Any] | None:
        """Get the policy assigned to a machine."""
        result: dict[str, Any] | None = await self._repository.get_assignment(machine_uuid)
        return result

    async def get_overrides(self, machine_uuid: str) -> list[dict[str, Any]]:
        """Get all overrides for a machine."""
        result: list[dict[str, Any]] = await self._repository.get_overrides(machine_uuid)
        return result

    async def get_metrics(self) -> dict[str, int]:
        """Get policy metrics snapshot."""
        counts = await self._repository.get_policy_count()
        assign_count = await self._repository.get_assignment_count()
        override_count = await self._repository.get_override_count()
        depth = self._inheritance.max_depth
        snap = self._metrics.snapshot(
            loaded_policies=counts,
            inheritance_depth=depth,
        )
        return {
            "loaded_policies": counts,
            "validation_failures": snap.validation_failures,
            "policy_assignments": assign_count,
            "overrides": override_count,
            "inheritance_depth": depth,
            "reloads": snap.reloads,
        }

    @staticmethod
    def _policy_to_schema(policy: Policy) -> PolicySchema:
        return PolicySchema(
            name=policy.name,
            description=policy.description,
            version=policy.version,
            parent=policy.parent,
            checksum=policy.checksum,
            heartbeat_interval_seconds=policy.heartbeat_interval_seconds,
            notification_retention_days=policy.notification_retention_days,
            log_retention_days=policy.log_retention_days,
            ip_masking_enabled=policy.ip_masking_enabled,
            maintenance_mode=policy.maintenance_mode,
            allowed_protocol_versions=list(policy.allowed_protocol_versions),
            feature_flags=FeatureFlagsSchema(
                discord=policy.feature_flags.discord,
                geoip=policy.feature_flags.geoip,
                docker=policy.feature_flags.docker,
                web_dashboard=policy.feature_flags.web_dashboard,
                remote_commands=policy.feature_flags.remote_commands,
                experimental=policy.feature_flags.experimental,
            ),
        )

    @staticmethod
    def _record_to_policy(record: dict[str, Any]) -> Policy:
        ff_data = {}
        if record.get("feature_flags_json"):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                ff_data = json.loads(record["feature_flags_json"])

        raw_data = {}
        if record.get("raw_yaml_json"):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                raw_data = json.loads(record["raw_yaml_json"])

        apv = ["1.0"]
        if record.get("allowed_protocol_versions"):
            try:
                apv = json.loads(record["allowed_protocol_versions"])
            except (json.JSONDecodeError, TypeError):
                apv = [record["allowed_protocol_versions"]]

        return Policy(
            name=record.get("name", ""),
            description=record.get("description", ""),
            version=str(record.get("version", "1")),
            parent=record.get("parent", "") or "",
            checksum=record.get("checksum", ""),
            heartbeat_interval_seconds=int(record.get("heartbeat_interval_seconds", 30)),
            notification_retention_days=int(record.get("notification_retention_days", 30)),
            log_retention_days=int(record.get("log_retention_days", 90)),
            ip_masking_enabled=bool(record.get("ip_masking_enabled", True)),
            maintenance_mode=bool(record.get("maintenance_mode", False)),
            allowed_protocol_versions=apv,
            feature_flags=FeatureFlagsSchema(**ff_data) if ff_data else FeatureFlagsSchema(),
            raw_yaml=raw_data,
        )
