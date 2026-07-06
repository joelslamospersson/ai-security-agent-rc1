"""
Machine Manager — high-level facade for the machine subsystem.

Coordinates registry, service, repository, and metrics.
Provides a single entry point for API handlers and app initialization.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.certificates.manager import CertificateManager
from management_server.machines.metrics import RegistryMetricsCollector
from management_server.machines.registry import MachineRegistry
from management_server.machines.repository import MachineRepository
from management_server.machines.schemas import RegistrationRequest, RegistrationResponse
from management_server.machines.service import RegistrationService
from management_server.machines.state_machine import MachineState, MachineStateMachine

logger = structlog.get_logger("machines.manager")


class MachineManager:
    """High-level facade for the machine subsystem."""

    def __init__(
        self,
        session: AsyncSession,
        cert_manager: CertificateManager,
    ) -> None:
        self._session = session
        self._cert_manager = cert_manager
        self._repository = MachineRepository(session)
        self._metrics = RegistryMetricsCollector()
        self._state_machine = MachineStateMachine()
        self._registry = MachineRegistry(
            repository=self._repository,
            state_machine=self._state_machine,
            metrics=self._metrics,
        )
        self._service = RegistrationService(
            registry=self._registry,
            repository=self._repository,
            cert_manager=cert_manager,
            metrics=self._metrics,
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the machine manager."""
        self._initialized = True
        logger.info("Machine manager initialized")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def registry(self) -> MachineRegistry:
        return self._registry

    @property
    def service(self) -> RegistrationService:
        return self._service

    @property
    def repository(self) -> MachineRepository:
        return self._repository

    @property
    def state_machine(self) -> MachineStateMachine:
        return self._state_machine

    @property
    def metrics(self) -> RegistryMetricsCollector:
        return self._metrics

    # --- Registration API ---

    async def create_registration(self, request: RegistrationRequest) -> RegistrationResponse:
        """Create a new registration request."""
        return await self._service.create_registration(request)

    async def approve(
        self,
        machine_uuid: str,
        approved_by: str = "admin",
        reason: str = "",
    ) -> RegistrationResponse:
        """Approve a registration and issue certificate."""
        return await self._service.approve(
            machine_uuid=machine_uuid,
            approved_by=approved_by,
            reason=reason,
        )

    async def reject(
        self,
        machine_uuid: str,
        rejected_by: str = "admin",
        reason: str = "",
    ) -> RegistrationResponse:
        """Reject a registration."""
        return await self._service.reject(
            machine_uuid=machine_uuid,
            rejected_by=rejected_by,
            reason=reason,
        )

    async def expire(self, machine_uuid: str) -> RegistrationResponse:
        """Expire a registration."""
        return await self._service.expire(machine_uuid)

    async def revoke(
        self,
        machine_uuid: str,
        revoked_by: str = "admin",
        reason: str = "",
    ) -> RegistrationResponse:
        """Revoke a machine."""
        return await self._service.revoke(
            machine_uuid=machine_uuid,
            revoked_by=revoked_by,
            reason=reason,
        )

    async def lookup(self, machine_uuid: str) -> dict[str, Any]:
        """Look up a machine."""
        result: dict[str, Any] = await self._service.lookup(machine_uuid)
        return result

    async def list_machines(
        self,
        status: MachineState | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """List machines."""
        result: dict[str, Any] = await self._service.list_machines(
            status=status, page=page, page_size=page_size
        )
        return result

    async def get_registration_request(self, machine_uuid: str) -> dict[str, Any] | None:
        """Get registration request record."""
        result: dict[str, Any] | None = await self._service.get_registration_request(machine_uuid)
        return result

    async def get_metrics(self) -> dict[str, int | float]:
        """Get system metrics."""
        result: dict[str, int | float] = await self._service.get_metrics()
        return result
