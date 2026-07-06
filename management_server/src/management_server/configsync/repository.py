"""
Config sync repository — append-only storage for packages and machine version tracking.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.configsync.exceptions import ConfigSyncRepositoryError
from management_server.configsync.models import ConfigurationPackage, PackageState

logger = structlog.get_logger("configsync.repository")


class ConfigSyncRepository:
    """Persists configuration packages and machine version state."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_package(self, package: ConfigurationPackage) -> dict[str, Any]:
        """Store a new configuration package."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                INSERT INTO configuration_packages (id, package_id, package_type, version,
                    format_type, state, checksum, signature, payload, metadata_json,
                    minimum_agent_version, rollback_version, base_package_id, created_at)
                VALUES (:id, :pid, :pt, :ver, :fmt, :state, :cs, :sig, :payload, :meta,
                    :mav, :rv, :bpid, :now)
            """),
            {
                "id": str(uuid.uuid4()),
                "pid": package.package_id,
                "pt": package.package_type.value,
                "ver": package.version,
                "fmt": package.format.value,
                "state": package.state.value,
                "cs": package.checksum,
                "sig": package.signature,
                "payload": package.payload,
                "meta": package.metadata_json,
                "mav": package.minimum_agent_version,
                "rv": package.rollback_version,
                "bpid": package.base_package_id,
                "now": now,
            },
        )
        await self._session.commit()
        return {"package_id": package.package_id}

    async def get_package(self, package_id: str) -> dict[str, Any] | None:
        """Get a package by ID."""
        result = await self._session.execute(
            text("SELECT * FROM configuration_packages WHERE package_id = :pid"),
            {"pid": package_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def list_packages(
        self,
        limit: int = 100,
        offset: int = 0,
        package_type: str | None = None,
        state: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List packages with optional filters."""
        where_parts: list[str] = []
        params: dict[str, object] = {}

        if package_type:
            where_parts.append("package_type = :pt")
            params["pt"] = package_type
        if state:
            where_parts.append("state = :state")
            params["state"] = state

        where = "WHERE " + " AND ".join(where_parts) if where_parts else ""

        count = await self._session.execute(
            text(f"SELECT COUNT(*) FROM configuration_packages {where}"), params
        )
        total = count.scalar() or 0

        params["limit"] = limit
        params["offset"] = offset
        result = await self._session.execute(
            text(
                f"SELECT * FROM configuration_packages {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        )
        return [dict(r._mapping) for r in result.fetchall()], total

    async def update_state(
        self,
        package_id: str,
        new_state: PackageState,
        triggered_by: str = "system",
        reason: str = "",
    ) -> dict[str, Any]:
        """Update package state and record in history."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                UPDATE configuration_packages
                SET state = :state, updated_at = :now
                WHERE package_id = :pid
            """),
            {"pid": package_id, "state": new_state.value, "now": now},
        )

        await self._session.execute(
            text("""
                INSERT INTO package_history (id, package_id, to_state, triggered_by, reason, created_at)
                VALUES (:id, :pid, :state, :by, :reason, :now)
            """),
            {
                "id": str(uuid.uuid4()),
                "pid": package_id,
                "state": new_state.value,
                "by": triggered_by,
                "reason": reason,
                "now": now,
            },
        )
        await self._session.commit()

        result = await self.get_package(package_id)
        if result is None:
            raise ConfigSyncRepositoryError(f"Package not found after update: {package_id}")
        return result

    async def get_available_packages(self) -> list[dict[str, Any]]:
        """Get all published/available packages."""
        result = await self._session.execute(
            text("""
                SELECT * FROM configuration_packages
                WHERE state IN ('published', 'available')
                ORDER BY created_at DESC
            """)
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def set_machine_version(self, machine_uuid: str, package_type: str, version: str) -> None:
        """Set or update machine version for a package type."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                INSERT INTO machine_package_versions (machine_uuid, package_type, current_version, last_sync_at)
                VALUES (:mu, :pt, :ver, :now)
                ON CONFLICT (machine_uuid, package_type) DO UPDATE SET
                    current_version = EXCLUDED.current_version,
                    last_sync_at = EXCLUDED.last_sync_at
            """),
            {"mu": machine_uuid, "pt": package_type, "ver": version, "now": now},
        )
        await self._session.commit()

    async def get_machine_versions(self, machine_uuid: str) -> list[dict[str, Any]]:
        """Get all version states for a machine."""
        result = await self._session.execute(
            text("""
                SELECT * FROM machine_package_versions
                WHERE machine_uuid = :mu
                ORDER BY package_type ASC
            """),
            {"mu": machine_uuid},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def count_packages(self) -> int:
        result = await self._session.execute(text("SELECT COUNT(*) FROM configuration_packages"))
        return result.scalar() or 0

    async def count_by_state(self) -> dict[str, int]:
        result = await self._session.execute(
            text("SELECT state, COUNT(*) as cnt FROM configuration_packages GROUP BY state")
        )
        counts: dict[str, int] = {}
        for row in result.fetchall():
            counts[row.state] = row.cnt
        return counts
