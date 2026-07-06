"""
Machine registry — authoritative inventory of all managed machines.

Provides core CRUD and state management operations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from management_server.machines.exceptions import (
    DuplicateMachineError,
    MachineNotFoundError,
)
from management_server.machines.metrics import RegistryMetricsCollector
from management_server.machines.repository import MachineRepository
from management_server.machines.state_machine import MachineState, MachineStateMachine

logger = structlog.get_logger("machines.registry")


class MachineRegistry:
    """Core machine registry — authoritative machine inventory."""

    def __init__(
        self,
        repository: MachineRepository,
        state_machine: MachineStateMachine | None = None,
        metrics: RegistryMetricsCollector | None = None,
    ) -> None:
        self._repository = repository
        self._state_machine = state_machine or MachineStateMachine()
        self._metrics = metrics or RegistryMetricsCollector()

    async def register(
        self,
        machine_uuid: str,
        hostname: str = "",
        operating_system: str = "",
        architecture: str = "",
        environment: str = "production",
        agent_version: str = "",
        public_key_fingerprint: str = "",
        public_key_pem: str = "",
    ) -> dict[str, Any]:
        """Register a new machine. Creates pending registration."""
        MachineStateMachine.validate_transition(
            MachineState.UNKNOWN, MachineState.PENDING_REGISTRATION
        )

        try:
            record = await self._repository.create_registration_request(
                machine_uuid=machine_uuid,
                hostname=hostname,
                operating_system=operating_system,
                architecture=architecture,
                environment=environment,
                agent_version=agent_version,
                public_key_fingerprint=public_key_fingerprint,
                public_key_pem=public_key_pem,
            )
        except DuplicateMachineError:
            raise

        self._state_machine.apply(
            MachineState.UNKNOWN,
            MachineState.PENDING_REGISTRATION,
            reason="New machine registration request",
            triggered_by="machine",
        )

        self._metrics.registration_requested()
        return self._to_machine_info(record)

    async def approve(
        self,
        machine_uuid: str,
        approved_by: str = "admin",
        reason: str = "",
        certificate_fingerprint: str = "",
    ) -> dict[str, Any]:
        """Approve a pending registration."""
        record = await self._get_record(machine_uuid)
        current_status = MachineState(record["status"])

        MachineStateMachine.validate_transition(current_status, MachineState.REGISTERED)

        now = datetime.now(tz=UTC)
        created_at = record.get("created_at")
        if isinstance(created_at, str):
            from dateutil import parser as dateutil_parser

            created_at = dateutil_parser.parse(created_at)
        approval_time = 0.0
        if created_at:
            approval_time = (now - created_at).total_seconds()

        updated = await self._repository.update_status(
            machine_uuid,
            MachineState.REGISTERED,
            approved_at=now,
        )

        if certificate_fingerprint:
            await self._repository.set_certificate_fingerprint(
                machine_uuid, certificate_fingerprint
            )

        self._state_machine.apply(
            current_status,
            MachineState.REGISTERED,
            reason=reason or f"Approved by {approved_by}",
            triggered_by=approved_by,
        )

        self._metrics.approved(approval_time)
        logger.info(
            "Machine approved",
            machine_uuid=machine_uuid,
            approved_by=approved_by,
            approval_time_ms=round(approval_time * 1000, 2),
        )

        return self._to_machine_info(updated)

    async def reject(
        self,
        machine_uuid: str,
        rejected_by: str = "admin",
        reason: str = "",
    ) -> dict[str, Any]:
        """Reject a pending registration."""
        record = await self._get_record(machine_uuid)
        current_status = MachineState(record["status"])

        MachineStateMachine.validate_transition(current_status, MachineState.REJECTED)

        updated = await self._repository.update_status(machine_uuid, MachineState.REJECTED)

        self._state_machine.apply(
            current_status,
            MachineState.REJECTED,
            reason=reason or f"Rejected by {rejected_by}",
            triggered_by=rejected_by,
        )

        self._metrics.rejected()
        logger.info("Machine rejected", machine_uuid=machine_uuid, reason=reason)

        return self._to_machine_info(updated)

    async def expire(self, machine_uuid: str) -> dict[str, Any]:
        """Mark a pending registration as expired."""
        record = await self._get_record(machine_uuid)
        current_status = MachineState(record["status"])

        MachineStateMachine.validate_transition(current_status, MachineState.EXPIRED)

        updated = await self._repository.update_status(machine_uuid, MachineState.EXPIRED)

        self._state_machine.apply(
            current_status,
            MachineState.EXPIRED,
            reason="Registration request expired",
            triggered_by="system",
        )

        self._metrics.expired()
        logger.info("Machine registration expired", machine_uuid=machine_uuid)

        return self._to_machine_info(updated)

    async def revoke(
        self,
        machine_uuid: str,
        revoked_by: str = "admin",
        reason: str = "",
    ) -> dict[str, Any]:
        """Revoke a registered machine."""
        record = await self._get_record(machine_uuid)
        current_status = MachineState(record["status"])

        MachineStateMachine.validate_transition(current_status, MachineState.REVOKED)

        updated = await self._repository.update_status(machine_uuid, MachineState.REVOKED)

        self._state_machine.apply(
            current_status,
            MachineState.REVOKED,
            reason=reason or f"Revoked by {revoked_by}",
            triggered_by=revoked_by,
        )

        self._metrics.revoked()
        logger.info("Machine revoked", machine_uuid=machine_uuid, reason=reason)

        return self._to_machine_info(updated)

    async def get_machine(self, machine_uuid: str) -> dict[str, Any]:
        """Get machine info. Raises MachineNotFoundError."""
        record = await self._repository.get_machine(machine_uuid)
        return self._to_machine_info(record)

    async def list_machines(
        self,
        status: MachineState | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """List machines with pagination."""
        machines, total = await self._repository.list_machines(
            status=status, page=page, page_size=page_size
        )
        return {
            "machines": [self._to_machine_info(m) for m in machines],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_metrics(self) -> dict[str, int | float]:
        """Get registry metrics snapshot."""
        counts = await self._repository.count_machines_by_status()
        total = sum(counts.values())
        pending = counts.get(MachineState.PENDING_REGISTRATION.value, 0)
        snapshot = self._metrics.snapshot(pending=pending, total_machines=total)
        return {
            "registrations_requested": snapshot.registrations_requested,
            "approved": snapshot.approved,
            "rejected": snapshot.rejected,
            "expired": snapshot.expired,
            "revoked": snapshot.revoked,
            "pending": pending,
            "total_machines": total,
            "average_approval_time_ms": snapshot.average_approval_time_ms,
        }

    async def _get_record(self, machine_uuid: str) -> dict[str, Any]:
        """Get a machine record or raise."""
        try:
            result: dict[str, Any] = await self._repository.get_machine(machine_uuid)
            return result
        except MachineNotFoundError as e:
            raise MachineNotFoundError(machine_uuid) from e

    @staticmethod
    def _to_machine_info(record: dict[str, Any]) -> dict[str, Any]:
        """Convert a DB record to a clean machine info dict."""
        return {
            "machine_uuid": record.get("machine_uuid", ""),
            "hostname": record.get("hostname", ""),
            "operating_system": record.get("operating_system", ""),
            "architecture": record.get("architecture", ""),
            "environment": record.get("environment", "production"),
            "agent_version": record.get("agent_version", ""),
            "public_key_fingerprint": record.get("public_key_fingerprint", ""),
            "certificate_fingerprint": record.get("certificate_fingerprint", ""),
            "status": record.get("status", "unknown"),
            "first_seen": _format_dt(record.get("first_seen")),
            "approved_at": _format_dt(record.get("approved_at")),
            "last_status_change": _format_dt(record.get("last_status_change")),
            "created_at": _format_dt(record.get("created_at")),
            "updated_at": _format_dt(record.get("updated_at")),
        }


def _format_dt(value: object) -> str | None:
    """Format a datetime value to ISO string, or return None."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
