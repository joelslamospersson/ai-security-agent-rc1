"""
Policy repository — database CRUD for policies, assignments, and overrides.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.policies.exceptions import PolicyRepositoryError
from management_server.policies.models import Policy

logger = structlog.get_logger("policies.repository")


class PolicyRepository:
    """Persists policies, machine assignments, and machine overrides."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_policy(self, policy: Policy) -> dict[str, Any]:
        """Save or update a policy definition."""
        now = datetime.now(tz=UTC)
        ff_json = json.dumps(policy.feature_flags.to_dict())
        raw_json = json.dumps(policy.raw_yaml)

        await self._session.execute(
            text("""
                INSERT INTO policies (name, description, version, parent, checksum,
                    heartbeat_interval_seconds, notification_retention_days, log_retention_days,
                    ip_masking_enabled, maintenance_mode, allowed_protocol_versions,
                    feature_flags_json, raw_yaml_json, created_at, updated_at)
                VALUES (:name, :desc, :ver, :parent, :cs,
                    :hb, :nr, :lr, :ipm, :mm, :apv,
                    :ffj, :ryj, :now, :now)
                ON CONFLICT (name) DO UPDATE SET
                    version = EXCLUDED.version,
                    checksum = EXCLUDED.checksum,
                    heartbeat_interval_seconds = EXCLUDED.heartbeat_interval_seconds,
                    feature_flags_json = EXCLUDED.feature_flags_json,
                    raw_yaml_json = EXCLUDED.raw_yaml_json,
                    updated_at = EXCLUDED.updated_at
            """),
            {
                "name": policy.name,
                "desc": policy.description,
                "ver": policy.version,
                "parent": policy.parent or None,
                "cs": policy.checksum,
                "hb": policy.heartbeat_interval_seconds,
                "nr": policy.notification_retention_days,
                "lr": policy.log_retention_days,
                "ipm": policy.ip_masking_enabled,
                "mm": policy.maintenance_mode,
                "apv": json.dumps(policy.allowed_protocol_versions),
                "ffj": ff_json,
                "ryj": raw_json,
                "now": now,
            },
        )
        await self._session.commit()
        get_result = await self._get_policy(policy.name)
        assert get_result is not None
        saved: dict[str, Any] = get_result
        return saved

    async def get_policy(self, name: str) -> dict[str, Any]:
        """Get a policy by name."""
        result = await self._get_policy(name)
        if result is None:
            raise PolicyRepositoryError(f"Policy not found: {name}")
        assert result is not None
        return result

    async def _get_policy(self, name: str) -> dict[str, Any] | None:
        result = await self._session.execute(
            text("SELECT * FROM policies WHERE name = :name"),
            {"name": name},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def list_policies(self) -> tuple[list[dict[str, Any]], int]:
        """List all policies."""
        result = await self._session.execute(text("SELECT * FROM policies ORDER BY name ASC"))
        rows = [dict(r._mapping) for r in result.fetchall()]
        return rows, len(rows)

    async def delete_policy(self, name: str) -> None:
        """Delete a policy."""
        await self._session.execute(
            text("DELETE FROM policies WHERE name = :name"),
            {"name": name},
        )
        await self._session.commit()

    async def assign_policy(
        self, machine_uuid: str, policy_name: str, assigned_by: str = "system"
    ) -> dict[str, Any]:
        """Assign a policy to a machine (upsert)."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                INSERT INTO machine_policy_assignments (machine_uuid, policy_name, assigned_at, assigned_by)
                VALUES (:mu, :pn, :now, :ab)
                ON CONFLICT (machine_uuid) DO UPDATE SET
                    policy_name = EXCLUDED.policy_name,
                    assigned_at = EXCLUDED.assigned_at,
                    assigned_by = EXCLUDED.assigned_by
            """),
            {"mu": machine_uuid, "pn": policy_name, "now": now, "ab": assigned_by},
        )
        await self._session.commit()
        return {
            "machine_uuid": machine_uuid,
            "policy_name": policy_name,
            "assigned_at": now.isoformat(),
        }

    async def get_assignment(self, machine_uuid: str) -> dict[str, Any] | None:
        """Get the policy assigned to a machine."""
        result = await self._session.execute(
            text("SELECT * FROM machine_policy_assignments WHERE machine_uuid = :mu"),
            {"mu": machine_uuid},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def set_override(
        self,
        machine_uuid: str,
        policy_name: str,
        key: str,
        value: str,
        original_value: str = "",
        created_by: str = "admin",
    ) -> dict[str, Any]:
        """Set a machine-specific override (upsert)."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                INSERT INTO machine_policy_overrides (machine_uuid, policy_name, key, value, original_value, created_by, created_at)
                VALUES (:mu, :pn, :key, :val, :ov, :cb, :now)
                ON CONFLICT (machine_uuid, key) DO UPDATE SET
                    value = EXCLUDED.value,
                    original_value = EXCLUDED.original_value,
                    created_by = EXCLUDED.created_by,
                    created_at = EXCLUDED.created_at
            """),
            {
                "mu": machine_uuid,
                "pn": policy_name,
                "key": key,
                "val": str(value),
                "ov": str(original_value),
                "cb": created_by,
                "now": now,
            },
        )
        await self._session.commit()
        return {
            "machine_uuid": machine_uuid,
            "key": key,
            "value": str(value),
            "created_at": now.isoformat(),
        }

    async def get_overrides(self, machine_uuid: str) -> list[dict[str, Any]]:
        """Get all overrides for a machine."""
        result = await self._session.execute(
            text(
                "SELECT * FROM machine_policy_overrides WHERE machine_uuid = :mu ORDER BY created_at DESC"
            ),
            {"mu": machine_uuid},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def get_policy_count(self) -> int:
        result = await self._session.execute(text("SELECT COUNT(*) FROM policies"))
        return result.scalar() or 0

    async def get_assignment_count(self) -> int:
        result = await self._session.execute(
            text("SELECT COUNT(*) FROM machine_policy_assignments")
        )
        return result.scalar() or 0

    async def get_override_count(self) -> int:
        result = await self._session.execute(text("SELECT COUNT(*) FROM machine_policy_overrides"))
        return result.scalar() or 0
