"""
Heartbeat repository — database CRUD for heartbeats, machine status, and capability history.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.heartbeat.models import MachineStatus, TimeoutConfig

logger = structlog.get_logger("heartbeat.repository")


class HeartbeatRepository:
    """Persists heartbeat records and machine status."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_heartbeat(
        self,
        machine_uuid: str,
        protocol_version: str,
        agent_version: str,
        hostname: str,
        environment: str,
        sequence_number: int,
        health_json: str = "",
        capabilities_json: str = "",
        queues_json: str = "",
        security_json: str = "",
        status: MachineStatus = MachineStatus.HEALTHY,
    ) -> dict[str, Any]:
        """Record a heartbeat and update machine status."""
        now = datetime.now(tz=UTC)
        hb_id = str(uuid.uuid4())

        # Insert heartbeat record
        await self._session.execute(
            text("""
                INSERT INTO heartbeats (id, machine_uuid, protocol_version, agent_version,
                    hostname, environment, sequence_number, status, health_json,
                    capabilities_json, queues_json, security_json, received_at, created_at)
                VALUES (:id, :machine_uuid, :protocol_version, :agent_version,
                    :hostname, :environment, :sequence_number, :status, :health_json,
                    :capabilities_json, :queues_json, :security_json, :received_at, :now)
            """),
            {
                "id": hb_id,
                "machine_uuid": machine_uuid,
                "protocol_version": protocol_version,
                "agent_version": agent_version,
                "hostname": hostname,
                "environment": environment,
                "sequence_number": sequence_number,
                "status": status.value,
                "health_json": health_json,
                "capabilities_json": capabilities_json,
                "queues_json": queues_json,
                "security_json": security_json,
                "received_at": now,
                "now": now,
            },
        )

        # Upsert machine status
        await self._session.execute(
            text("""
                INSERT INTO machine_status (machine_uuid, status, last_heartbeat_at,
                    protocol_version, agent_version, hostname, environment,
                    last_sequence_number, created_at, updated_at)
                VALUES (:mu, :status, :now, :pv, :av, :hn, :env, :seq, :now, :now)
                ON CONFLICT (machine_uuid) DO UPDATE SET
                    status = :status,
                    last_heartbeat_at = :now,
                    protocol_version = :pv,
                    agent_version = :av,
                    hostname = :hn,
                    environment = :env,
                    last_sequence_number = :seq,
                    updated_at = :now
            """),
            {
                "mu": machine_uuid,
                "status": status.value,
                "now": now,
                "pv": protocol_version,
                "av": agent_version,
                "hn": hostname,
                "env": environment,
                "seq": sequence_number,
            },
        )

        await self._session.commit()

        return {
            "id": hb_id,
            "machine_uuid": machine_uuid,
            "status": status.value,
            "received_at": now.isoformat(),
        }

    async def get_last_heartbeat(self, machine_uuid: str) -> dict[str, Any] | None:
        """Get the most recent heartbeat for a machine."""
        result = await self._session.execute(
            text("""
                SELECT * FROM heartbeats
                WHERE machine_uuid = :mu
                ORDER BY received_at DESC
                LIMIT 1
            """),
            {"mu": machine_uuid},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def get_machine_status(self, machine_uuid: str) -> dict[str, Any] | None:
        """Get current machine status record."""
        result = await self._session.execute(
            text("SELECT * FROM machine_status WHERE machine_uuid = :mu"),
            {"mu": machine_uuid},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def get_last_sequence_number(self, machine_uuid: str) -> int | None:
        """Get the last sequence number for a machine."""
        result = await self._session.execute(
            text("""
                SELECT last_sequence_number FROM machine_status
                WHERE machine_uuid = :mu
            """),
            {"mu": machine_uuid},
        )
        row = result.fetchone()
        if row is None:
            return None
        seq_val: int = row.last_sequence_number
        return seq_val

    async def update_machine_status(self, machine_uuid: str, status: MachineStatus) -> None:
        """Update machine status (e.g., to OFFLINE)."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                UPDATE machine_status
                SET status = :status, updated_at = :now
                WHERE machine_uuid = :mu
            """),
            {"mu": machine_uuid, "status": status.value, "now": now},
        )
        await self._session.commit()

    async def detect_offline_machines(self, timeout_config: TimeoutConfig) -> list[dict[str, Any]]:
        """Find machines that haven't heartbeated within thresholds.

        Returns list of (machine_uuid, old_status, new_status).
        """
        now = datetime.now(tz=UTC)
        results: list[dict[str, Any]] = []

        # DELAYED: healthy machines that missed their window
        delayed_threshold = now - timedelta(seconds=timeout_config.healthy_timeout_seconds)
        delayed = await self._session.execute(
            text("""
                UPDATE machine_status
                SET status = 'delayed', updated_at = :now
                WHERE status = 'healthy' AND last_heartbeat_at < :threshold
                RETURNING machine_uuid, status
            """),
            {"now": now, "threshold": delayed_threshold},
        )
        for row in delayed.fetchall():
            results.append(
                {"machine_uuid": row.machine_uuid, "old_status": "healthy", "new_status": "delayed"}
            )

        # OFFLINE: delayed machines that missed further
        offline_threshold = now - timedelta(seconds=timeout_config.delayed_timeout_seconds)
        offline = await self._session.execute(
            text("""
                UPDATE machine_status
                SET status = 'offline', updated_at = :now
                WHERE status = 'delayed' AND last_heartbeat_at < :threshold
                RETURNING machine_uuid, status
            """),
            {"now": now, "threshold": offline_threshold},
        )
        for row in offline.fetchall():
            results.append(
                {"machine_uuid": row.machine_uuid, "old_status": "delayed", "new_status": "offline"}
            )

        await self._session.commit()
        return results

    async def record_capability_change(
        self,
        machine_uuid: str,
        capability: str,
        change_type: str,
        old_value: object = None,
        new_value: object = None,
    ) -> None:
        """Record a capability change event."""
        await self._session.execute(
            text("""
                INSERT INTO capability_history (id, machine_uuid, capability,
                    change_type, old_value, new_value, created_at)
                VALUES (:id, :mu, :cap, :ct, :ov, :nv, :now)
            """),
            {
                "id": str(uuid.uuid4()),
                "mu": machine_uuid,
                "cap": capability,
                "ct": change_type,
                "ov": json.dumps(old_value) if old_value is not None else None,
                "nv": json.dumps(new_value) if new_value is not None else None,
                "now": datetime.now(tz=UTC),
            },
        )
        await self._session.commit()

    async def get_capability_snapshot(self, machine_uuid: str) -> dict[str, bool] | None:
        """Get the last capabilities snapshot for a machine from heartbeats."""
        result = await self._session.execute(
            text("""
                SELECT capabilities_json FROM heartbeats
                WHERE machine_uuid = :mu AND capabilities_json != ''
                ORDER BY received_at DESC
                LIMIT 1
            """),
            {"mu": machine_uuid},
        )
        row = result.fetchone()
        if row is None:
            return None
        try:
            parsed_data: dict[str, bool] = json.loads(row.capabilities_json)
            return parsed_data
        except (json.JSONDecodeError, TypeError):
            return None

    async def get_heartbeat_count(self) -> int:
        """Get total heartbeat count."""
        result = await self._session.execute(text("SELECT COUNT(*) FROM heartbeats"))
        return result.scalar() or 0

    async def get_status_counts(self) -> dict[str, int]:
        """Get machine status counts."""
        result = await self._session.execute(
            text("""
                SELECT status, COUNT(*) as cnt
                FROM machine_status
                GROUP BY status
            """)
        )
        counts: dict[str, int] = {}
        for row in result.fetchall():
            counts[row.status] = row.cnt
        return counts

    async def get_machines_by_status(self, status: MachineStatus) -> list[dict[str, Any]]:
        """Get all machines with a given status."""
        result = await self._session.execute(
            text("""
                SELECT * FROM machine_status
                WHERE status = :status
                ORDER BY last_heartbeat_at DESC
            """),
            {"status": status.value},
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def get_latest_capabilities_json(self, machine_uuid: str) -> str:
        """Get the latest capabilities JSON for a machine."""
        result = await self._session.execute(
            text("""
                SELECT capabilities_json FROM heartbeats
                WHERE machine_uuid = :mu AND capabilities_json != ''
                ORDER BY received_at DESC
                LIMIT 1
            """),
            {"mu": machine_uuid},
        )
        row = result.fetchone()
        if row is None:
            return ""
        return row.capabilities_json or ""
