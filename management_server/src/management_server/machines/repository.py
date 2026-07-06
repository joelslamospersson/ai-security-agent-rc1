"""
Machine repository — database CRUD for machines and registration requests.

Uses raw SQL via SQLAlchemy async sessions for performance and clarity.
All public methods return plain dicts for maximum flexibility.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.machines.exceptions import (
    DuplicateMachineError,
    MachineNotFoundError,
)
from management_server.machines.state_machine import MachineState

logger = structlog.get_logger("machines.repository")


class MachineRepository:
    """Persists machine records and registration requests."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Registration Requests ──────────────────────────────────────────────

    async def create_registration_request(
        self,
        machine_uuid: str,
        hostname: str,
        operating_system: str,
        architecture: str,
        environment: str,
        agent_version: str,
        public_key_fingerprint: str,
        public_key_pem: str,
    ) -> dict[str, Any]:
        """Create a new registration request. Raises DuplicateMachineError if exists."""
        existing = await self._get_machine(machine_uuid)
        if existing is not None:
            raise DuplicateMachineError(machine_uuid)

        now = datetime.now(UTC)
        row_id = str(uuid.uuid4())

        await self._session.execute(
            text("""
                INSERT INTO machines (id, machine_uuid, hostname, operating_system, architecture,
                    environment, agent_version, public_key_fingerprint, public_key_pem,
                    status, first_seen, last_status_change, created_at, updated_at)
                VALUES (:id, :machine_uuid, :hostname, :os, :arch,
                    :env, :agent, :pk_fp, :pk_pem,
                    :status, :first_seen, :last_status_change, :now, :now)
            """),
            {
                "id": row_id,
                "machine_uuid": machine_uuid,
                "hostname": hostname,
                "os": operating_system,
                "arch": architecture,
                "env": environment,
                "agent": agent_version,
                "pk_fp": public_key_fingerprint,
                "pk_pem": public_key_pem,
                "status": MachineState.PENDING_REGISTRATION.value,
                "first_seen": now,
                "last_status_change": now,
                "now": now,
            },
        )

        await self._session.execute(
            text("""
                INSERT INTO registration_requests (id, machine_uuid, status,
                    public_key_pem, created_at, updated_at)
                VALUES (:id, :machine_uuid, :status, :public_key_pem, :now, :now)
            """),
            {
                "id": str(uuid.uuid4()),
                "machine_uuid": machine_uuid,
                "status": "pending",
                "public_key_pem": public_key_pem,
                "now": now,
            },
        )

        await self._session.commit()
        logger.info("Registration request created", machine_uuid=machine_uuid)

        result = await self._get_machine(machine_uuid)
        assert result is not None
        return result

    async def get_registration_request(self, machine_uuid: str) -> dict[str, Any] | None:
        """Get a registration request record."""
        result = await self._session.execute(
            text("SELECT * FROM registration_requests WHERE machine_uuid = :uuid"),
            {"uuid": machine_uuid},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def get_all_pending(self) -> list[dict[str, Any]]:
        """Get all machines with pending registration."""
        result = await self._session.execute(
            text("""
                SELECT * FROM machines
                WHERE status = 'pending_registration'
                ORDER BY created_at ASC
            """)
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def count_registrations(self) -> dict[str, int]:
        """Count registration requests by status."""
        result = await self._session.execute(
            text("""
                SELECT status, COUNT(*) as cnt
                FROM registration_requests
                GROUP BY status
            """)
        )
        counts: dict[str, int] = {}
        for row in result.fetchall():
            counts[row.status] = row.cnt
        return counts

    # ── Machine CRUD ───────────────────────────────────────────────────────

    async def get_machine(self, machine_uuid: str) -> dict[str, Any]:
        """Get a machine record. Raises MachineNotFoundError if absent."""
        result = await self._get_machine(machine_uuid)
        if result is None:
            raise MachineNotFoundError(machine_uuid)
        return result

    async def _get_machine(self, machine_uuid: str) -> dict[str, Any] | None:
        """Internal — get machine dict or None."""
        result = await self._session.execute(
            text("SELECT * FROM machines WHERE machine_uuid = :uuid"),
            {"uuid": machine_uuid},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def update_status(
        self,
        machine_uuid: str,
        new_status: MachineState,
        approved_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Update machine status. Raises MachineNotFoundError if absent."""
        now = datetime.now(UTC)
        if approved_at is None and new_status == MachineState.REGISTERED:
            approved_at = now

        await self._session.execute(
            text("""
                UPDATE machines
                SET status = :status,
                    last_status_change = :now,
                    approved_at = COALESCE(:approved_at, approved_at),
                    updated_at = :now
                WHERE machine_uuid = :uuid
            """),
            {
                "uuid": machine_uuid,
                "status": new_status.value,
                "now": now,
                "approved_at": approved_at,
            },
        )

        if new_status in (MachineState.REGISTERED, MachineState.REJECTED, MachineState.EXPIRED):
            await self._session.execute(
                text("""
                    UPDATE registration_requests
                    SET status = :status, updated_at = :now
                    WHERE machine_uuid = :uuid
                """),
                {"uuid": machine_uuid, "status": new_status.value, "now": now},
            )

        await self._session.commit()
        logger.info(
            "Machine status updated",
            machine_uuid=machine_uuid,
            new_status=new_status.value,
        )

        result = await self._get_machine(machine_uuid)
        if result is None:
            raise MachineNotFoundError(machine_uuid)
        return result

    async def set_certificate_fingerprint(self, machine_uuid: str, fingerprint: str) -> None:
        """Store the issued certificate fingerprint."""
        await self._session.execute(
            text("""
                UPDATE machines
                SET certificate_fingerprint = :fp, updated_at = :now
                WHERE machine_uuid = :uuid
            """),
            {"uuid": machine_uuid, "fp": fingerprint, "now": datetime.now(UTC)},
        )
        await self._session.commit()

    async def list_machines(
        self,
        status: MachineState | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        """List machines with optional status filter and pagination."""
        offset = (page - 1) * page_size
        where = "WHERE status = :status" if status else ""
        params: dict[str, object] = {}
        if status:
            params["status"] = status.value

        count_result = await self._session.execute(
            text(f"SELECT COUNT(*) FROM machines {where}"),
            params,
        )
        total = count_result.scalar() or 0

        params["limit"] = page_size
        params["offset"] = offset
        result = await self._session.execute(
            text(
                f"SELECT * FROM machines {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        )
        machines = [dict(row._mapping) for row in result.fetchall()]
        return machines, total

    async def find_by_hostname(self, hostname: str) -> dict[str, Any] | None:
        """Find a machine by hostname."""
        result = await self._session.execute(
            text("SELECT * FROM machines WHERE hostname = :hostname LIMIT 1"),
            {"hostname": hostname},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def delete_machine(self, machine_uuid: str) -> None:
        """Delete a machine record (hard delete for testing/cleanup)."""
        await self._session.execute(
            text("DELETE FROM machines WHERE machine_uuid = :uuid"),
            {"uuid": machine_uuid},
        )
        await self._session.execute(
            text("DELETE FROM registration_requests WHERE machine_uuid = :uuid"),
            {"uuid": machine_uuid},
        )
        await self._session.commit()

    async def count_machines_by_status(self) -> dict[str, int]:
        """Count machines grouped by status."""
        result = await self._session.execute(
            text("""
                SELECT status, COUNT(*) as cnt
                FROM machines
                GROUP BY status
            """)
        )
        counts: dict[str, int] = {}
        for row in result.fetchall():
            counts[row.status] = row.cnt
        return counts
