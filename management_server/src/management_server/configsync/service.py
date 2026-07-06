"""
Config sync service — orchestrates package creation, lifecycle, and version tracking.
"""

from __future__ import annotations

from typing import Any

import structlog

from management_server.configsync.exceptions import PackageNotFoundError
from management_server.configsync.lifecycle import PackageLifecycle
from management_server.configsync.metrics import ConfigSyncMetricsCollector
from management_server.configsync.models import (
    ConfigurationPackage,
    PackageFormat,
    PackageState,
    PackageType,
)
from management_server.configsync.repository import ConfigSyncRepository
from management_server.configsync.schemas import (
    AvailablePackageSchema,
    CreatePackageRequest,
    PackageSchema,
)
from management_server.configsync.validator import PackageValidator

logger = structlog.get_logger("configsync.service")


class ConfigSyncService:
    """Configuration Synchronization Framework service."""

    def __init__(
        self,
        repository: ConfigSyncRepository,
        metrics: ConfigSyncMetricsCollector | None = None,
    ) -> None:
        self._repository = repository
        self._metrics = metrics or ConfigSyncMetricsCollector()

    async def create_package(self, request: CreatePackageRequest) -> PackageSchema:
        """Create a new configuration package."""
        PackageValidator.validate_and_raise(
            package_type=request.package_type,
            version=request.version,
            payload=request.payload,
            format_type=request.format_type,
        )

        package = ConfigurationPackage.create(
            package_type=request.package_type,
            version=request.version,
            payload=request.payload,
            metadata=request.metadata,
            minimum_agent_version=request.minimum_agent_version,
            rollback_version=request.rollback_version,
            format_type=PackageFormat(request.format_type),
            base_package_id=request.base_package_id,
        )

        await self._repository.create_package(package)
        self._metrics.package_created()

        logger.info("Package created", package_id=package.package_id, type=request.package_type)

        return self._to_schema(package)

    async def publish_package(self, package_id: str, published_by: str = "admin") -> PackageSchema:
        """Publish a package (SIGNED → PUBLISHED → AVAILABLE)."""
        record = await self._get_record(package_id)
        current = PackageState(record["state"])

        PackageLifecycle.validate(current, PackageState.SIGNED)
        await self._repository.update_state(package_id, PackageState.SIGNED, published_by)

        PackageLifecycle.validate(PackageState.SIGNED, PackageState.PUBLISHED)
        await self._repository.update_state(package_id, PackageState.PUBLISHED, published_by)

        PackageLifecycle.validate(PackageState.PUBLISHED, PackageState.AVAILABLE)
        updated = await self._repository.update_state(
            package_id, PackageState.AVAILABLE, published_by
        )

        self._metrics.package_published()
        logger.info("Package published", package_id=package_id, by=published_by)

        return self._record_to_schema(updated)

    async def get_package(self, package_id: str) -> PackageSchema | None:
        """Get a package by ID."""
        record = await self._repository.get_package(package_id)
        if record is None:
            return None
        return self._record_to_schema(record)

    async def list_packages(
        self,
        limit: int = 100,
        offset: int = 0,
        package_type: str | None = None,
        state: str | None = None,
    ) -> dict[str, Any]:
        """List packages with filters."""
        records, total = await self._repository.list_packages(
            limit=limit,
            offset=offset,
            package_type=package_type,
            state=state,
        )
        packages = [self._record_to_schema(r) for r in records]
        return {"packages": packages, "total": total}

    async def get_available_for_heartbeat(
        self, machine_uuid: str, agent_version: str = ""
    ) -> list[AvailablePackageSchema]:
        """Get available packages for a machine (heartbeat advertisement)."""
        self._metrics.sync_requested()

        records = await self._repository.get_available_packages()
        packages: list[ConfigurationPackage] = []
        for r in records:
            packages.append(
                ConfigurationPackage(
                    package_id=r.get("package_id", ""),
                    package_type=PackageType(r.get("package_type", "configuration")),
                    version=str(r.get("version", "1")),
                    format=PackageFormat(r.get("format_type", "full")),
                    state=PackageState(r.get("state", "available")),
                    checksum=r.get("checksum", ""),
                    minimum_agent_version=r.get("minimum_agent_version", ""),
                    rollback_version=r.get("rollback_version", ""),
                )
            )

        machine_versions = await self._repository.get_machine_versions(machine_uuid)
        current_versions: dict[str, str] = {
            mv["package_type"]: mv["current_version"] for mv in machine_versions
        }

        available = PackageValidator.get_available_for_agent(
            packages, agent_version, current_versions
        )

        return [
            AvailablePackageSchema(
                package_id=p.package_id,
                package_type=p.package_type.value,
                version=p.version,
                format=p.format.value,
                checksum=p.checksum,
                minimum_agent_version=p.minimum_agent_version,
                rollback_version=p.rollback_version,
            )
            for p in available
        ]

    async def get_machine_versions(self, machine_uuid: str) -> list[dict[str, Any]]:
        """Get version state for a machine."""
        result: list[dict[str, Any]] = await self._repository.get_machine_versions(machine_uuid)
        return result

    async def get_metrics(self) -> dict[str, int]:
        """Get config sync metrics."""
        total = await self._repository.count_packages()
        counts = await self._repository.count_by_state()
        snap = self._metrics.snapshot()
        metrics_result: dict[str, int] = {
            "packages_created": total,
            "packages_published": snap.packages_published,
            "packages_downloaded": snap.packages_downloaded,
            "package_failures": snap.package_failures,
            "synchronization_requests": snap.synchronization_requests,
            "version_mismatches": snap.version_mismatches,
        }
        for k, v in counts.items():
            metrics_result[f"state_{k}"] = v
        return metrics_result

    async def _get_record(self, package_id: str) -> dict[str, Any]:
        record = await self._repository.get_package(package_id)
        if record is None:
            raise PackageNotFoundError(package_id)
        record_result: dict[str, Any] = record
        return record_result

    @staticmethod
    def _to_schema(package: ConfigurationPackage) -> PackageSchema:
        return PackageSchema(
            package_id=package.package_id,
            package_type=package.package_type.value,
            version=package.version,
            format=package.format.value,
            state=package.state.value,
            checksum=package.checksum,
            signature=package.signature,
            minimum_agent_version=package.minimum_agent_version,
            rollback_version=package.rollback_version,
            created_at=package.created_at,
        )

    @staticmethod
    def _record_to_schema(record: dict[str, Any]) -> PackageSchema:
        return PackageSchema(
            package_id=record.get("package_id", ""),
            package_type=record.get("package_type", "configuration"),
            version=str(record.get("version", "1")),
            format=record.get("format_type", "full"),
            state=record.get("state", "created"),
            checksum=record.get("checksum", ""),
            signature=record.get("signature", ""),
            minimum_agent_version=record.get("minimum_agent_version", ""),
            rollback_version=record.get("rollback_version", ""),
            created_at=record.get("created_at"),
        )
