"""
Config Sync Manager — high-level facade.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.configsync.metrics import ConfigSyncMetricsCollector
from management_server.configsync.repository import ConfigSyncRepository
from management_server.configsync.schemas import (
    AvailablePackageSchema,
    CreatePackageRequest,
    PackageSchema,
)
from management_server.configsync.service import ConfigSyncService

logger = structlog.get_logger("configsync.manager")


class ConfigSyncManager:
    """High-level facade for the Configuration Synchronization Framework."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = ConfigSyncRepository(session)
        self._metrics = ConfigSyncMetricsCollector()
        self._service = ConfigSyncService(repository=self._repository, metrics=self._metrics)
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("Config sync manager initialized")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def service(self) -> ConfigSyncService:
        return self._service

    async def create_package(self, request: CreatePackageRequest) -> PackageSchema:
        return await self._service.create_package(request)

    async def publish_package(self, package_id: str, published_by: str = "admin") -> PackageSchema:
        return await self._service.publish_package(package_id, published_by)

    async def get_package(self, package_id: str) -> PackageSchema | None:
        return await self._service.get_package(package_id)

    async def list_packages(
        self,
        limit: int = 100,
        offset: int = 0,
        package_type: str | None = None,
        state: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = await self._service.list_packages(
            limit=limit,
            offset=offset,
            package_type=package_type,
            state=state,
        )
        return result

    async def get_available_for_heartbeat(
        self, machine_uuid: str, agent_version: str = ""
    ) -> list[AvailablePackageSchema]:
        result: list[AvailablePackageSchema] = await self._service.get_available_for_heartbeat(
            machine_uuid,
            agent_version,
        )
        return result

    async def get_machine_versions(self, machine_uuid: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._service.get_machine_versions(machine_uuid)
        return result

    async def get_metrics(self) -> dict[str, int]:
        result: dict[str, int] = await self._service.get_metrics()
        return result
