"""
AuditEvent factory — simplifies creating audit events from all subsystems.
"""

from __future__ import annotations

from typing import Any

import structlog

from management_server.audit.models import AuditEvent, AuditOutcome, AuditSeverity

logger = structlog.get_logger("audit.event")


class AuditEventFactory:
    """Factory for creating AuditEvent instances."""

    @staticmethod
    def create(
        subsystem: str,
        event_type: str,
        description: str = "",
        machine_id: str = "",
        actor: str = "system",
        severity: AuditSeverity = AuditSeverity.INFO,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        correlation_id: str = "",
        metadata: dict[str, Any] | None = None,
        previous_hash: str = "",
    ) -> AuditEvent:
        return AuditEvent.create(
            subsystem=subsystem,
            event_type=event_type,
            description=description,
            machine_id=machine_id,
            actor=actor,
            severity=severity,
            outcome=outcome,
            correlation_id=correlation_id,
            metadata=metadata,
            previous_hash=previous_hash,
        )

    @staticmethod
    def success(
        subsystem: str,
        event_type: str,
        description: str = "",
        machine_id: str = "",
        actor: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return AuditEvent.create(
            subsystem=subsystem,
            event_type=event_type,
            description=description,
            machine_id=machine_id,
            actor=actor,
            severity=AuditSeverity.INFO,
            outcome=AuditOutcome.SUCCESS,
            metadata=metadata,
        )

    @staticmethod
    def failure(
        subsystem: str,
        event_type: str,
        description: str = "",
        machine_id: str = "",
        actor: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return AuditEvent.create(
            subsystem=subsystem,
            event_type=event_type,
            description=description,
            machine_id=machine_id,
            actor=actor,
            severity=AuditSeverity.ERROR,
            outcome=AuditOutcome.FAILURE,
            metadata=metadata,
        )

    @staticmethod
    def warning(
        subsystem: str,
        event_type: str,
        description: str = "",
        machine_id: str = "",
        actor: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return AuditEvent.create(
            subsystem=subsystem,
            event_type=event_type,
            description=description,
            machine_id=machine_id,
            actor=actor,
            severity=AuditSeverity.WARNING,
            outcome=AuditOutcome.SKIPPED,
            metadata=metadata,
        )
