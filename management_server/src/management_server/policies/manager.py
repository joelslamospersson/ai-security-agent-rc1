"""
Policy Manager — high-level facade for the Policy Engine.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.policies.inheritance import PolicyInheritanceEngine
from management_server.policies.loader import PolicyLoader
from management_server.policies.metrics import PolicyMetricsCollector
from management_server.policies.repository import PolicyRepository
from management_server.policies.schemas import (
    PolicyAssignRequest,
    PolicyOverrideRequest,
    PolicySchema,
    PolicyValidateResponse,
)
from management_server.policies.service import PolicyService
from management_server.policies.validator import PolicyValidator

logger = structlog.get_logger("policies.manager")


class PolicyManager:
    """High-level facade for the Policy Engine."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session
        self._repository = PolicyRepository(session)
        self._loader = PolicyLoader()
        self._inheritance = PolicyInheritanceEngine()
        self._metrics = PolicyMetricsCollector()
        self._validator = PolicyValidator()
        self._service = PolicyService(
            repository=self._repository,
            loader=self._loader,
            inheritance=self._inheritance,
            metrics=self._metrics,
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the policy manager: load and validate all policies."""
        schemas = await self._service.load_policies()
        logger.info("Policy manager initialized", count=len(schemas))
        self._initialized = True

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def service(self) -> PolicyService:
        return self._service

    async def get_policy(self, name: str) -> PolicySchema:
        result: PolicySchema = await self._service.get_policy(name)
        return result

    async def list_policies(self) -> list[PolicySchema]:
        result: list[PolicySchema] = await self._service.list_policies()
        return result

    async def validate_policy_yaml(self, name: str, yaml_string: str) -> PolicyValidateResponse:
        return await self._service.validate_policy_yaml(name, yaml_string)

    async def assign_policy(self, request: PolicyAssignRequest) -> dict[str, Any]:
        result: dict[str, Any] = await self._service.assign_policy(
            request.machine_uuid,
            "default",
            request.assigned_by,
        )
        return result

    async def assign_policy_named(
        self, machine_uuid: str, policy_name: str, assigned_by: str = "system"
    ) -> dict[str, Any]:
        result: dict[str, Any] = await self._service.assign_policy(
            machine_uuid, policy_name, assigned_by
        )
        return result

    async def set_override(self, request: PolicyOverrideRequest) -> dict[str, Any]:
        result: dict[str, Any] = await self._service.set_override(
            machine_uuid=request.machine_uuid,
            policy_name="",
            key=request.key,
            value=request.value,
            created_by=request.created_by,
        )
        return result

    async def get_assignment(self, machine_uuid: str) -> dict[str, Any] | None:
        result: dict[str, Any] | None = await self._service.get_assignment(machine_uuid)
        return result

    async def get_overrides(self, machine_uuid: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._service.get_overrides(machine_uuid)
        return result

    async def get_metrics(self) -> dict[str, int]:
        result: dict[str, int] = await self._service.get_metrics()
        return result
