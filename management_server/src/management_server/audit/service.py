"""
Audit service — orchestrates audit event creation, validation, persistence, and export.
"""

from datetime import UTC, datetime
from typing import Any

import structlog

from management_server.audit.exceptions import AuditValidationError
from management_server.audit.exporter import ExportRegistry
from management_server.audit.metrics import AuditMetricsCollector
from management_server.audit.models import AuditEvent, AuditOutcome, AuditSeverity
from management_server.audit.repository import AuditRepository
from management_server.audit.retention import RetentionCalculator, RetentionReport
from management_server.audit.schemas import (
    AuditEventSchema,
    AuditExportResponse,
    AuditVerifyResponse,
)
from management_server.audit.validator import AuditValidator

logger = structlog.get_logger("audit.service")


class AuditService:
    """Audit Engine service."""

    def __init__(
        self,
        repository: AuditRepository,
        retention_calculator: RetentionCalculator | None = None,
        export_registry: ExportRegistry | None = None,
        metrics: AuditMetricsCollector | None = None,
    ) -> None:
        self._repository = repository
        self._retention = retention_calculator or RetentionCalculator()
        self._export_registry = export_registry or ExportRegistry()
        self._metrics = metrics or AuditMetricsCollector()

    async def record(
        self,
        subsystem: str,
        event_type: str,
        description: str = "",
        machine_id: str = "",
        actor: str = "system",
        severity: AuditSeverity = AuditSeverity.INFO,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        correlation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEventSchema:
        """Record an audit event with hash chaining."""
        # Get the last event's hash for chaining
        last = await self._repository.get_last()
        previous_hash = last["current_hash"] if last else ""

        event = AuditEvent.create(
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

        errors = AuditValidator.validate(event)
        if errors:
            self._metrics.validation_failure()
            raise AuditValidationError(errors[0])

        await self._repository.append(event)
        self._metrics.event_written()

        logger.info(
            "Audit event recorded",
            audit_id=event.audit_id,
            subsystem=subsystem,
            event_type=event_type,
        )

        return self._to_schema(event)

    async def get_event(self, audit_id: str) -> AuditEventSchema | None:
        """Get an audit event by ID."""
        record = await self._repository.get(audit_id)
        if record is None:
            return None
        return AuditEventSchema(
            audit_id=record.get("audit_id", ""),
            correlation_id=record.get("correlation_id", ""),
            timestamp=record.get("timestamp"),
            machine_id=record.get("machine_id", ""),
            subsystem=record.get("subsystem", ""),
            actor=record.get("actor", "system"),
            event_type=record.get("event_type", ""),
            severity=record.get("severity", "info"),
            outcome=record.get("outcome", "success"),
            description=record.get("description", ""),
            metadata_json=record.get("metadata_json", "{}"),
            current_hash=record.get("current_hash", ""),
            previous_hash=record.get("previous_hash", ""),
        )

    async def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        subsystem: str | None = None,
        event_type: str | None = None,
    ) -> dict[str, Any]:
        """List audit events with filters."""
        records, total = await self._repository.get_ordered(
            limit=limit,
            offset=offset,
            subsystem=subsystem,
            event_type=event_type,
        )
        events = []
        for r in records:
            events.append(
                AuditEventSchema(
                    audit_id=r.get("audit_id", ""),
                    correlation_id=r.get("correlation_id", ""),
                    timestamp=r.get("timestamp"),
                    machine_id=r.get("machine_id", ""),
                    subsystem=r.get("subsystem", ""),
                    actor=r.get("actor", "system"),
                    event_type=r.get("event_type", ""),
                    severity=r.get("severity", "info"),
                    outcome=r.get("outcome", "success"),
                    description=r.get("description", ""),
                    current_hash=r.get("current_hash", ""),
                    previous_hash=r.get("previous_hash", ""),
                )
            )
        return {"events": events, "total": total}

    async def verify_integrity(self) -> AuditVerifyResponse:
        """Verify the entire audit hash chain."""
        records, total = await self._repository.get_ordered(limit=1000000)

        if total == 0:
            return AuditVerifyResponse(verified=True, total_events=0)

        events: list[AuditEvent] = []
        for r in records:
            ts = r.get("timestamp")
            if isinstance(ts, str):
                from dateutil import parser as dateutil_parser

                ts = dateutil_parser.parse(ts)
            events.append(
                AuditEvent(
                    audit_id=r.get("audit_id", ""),
                    correlation_id=r.get("correlation_id", ""),
                    timestamp=ts or datetime.now(tz=UTC),
                    machine_id=r.get("machine_id", ""),
                    subsystem=r.get("subsystem", ""),
                    actor=r.get("actor", "system"),
                    event_type=r.get("event_type", ""),
                    severity=AuditSeverity(r.get("severity", "info")),
                    outcome=AuditOutcome(r.get("outcome", "success")),
                    description=r.get("description", ""),
                    metadata_json=r.get("metadata_json", "{}"),
                    current_hash=r.get("current_hash", ""),
                    previous_hash=r.get("previous_hash", ""),
                )
            )

        valid, failed_id = AuditValidator.verify_chain(events)
        if not valid:
            self._metrics.hash_failure()

        verified = sum(1 for e in events if e.verify_integrity())
        return AuditVerifyResponse(
            verified=valid,
            total_events=total,
            verified_events=verified,
            failed_events=total - verified,
            first_failure_id=failed_id,
        )

    async def export_events(
        self,
        format_name: str = "json",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        subsystem: str | None = None,
        event_type: str | None = None,
    ) -> AuditExportResponse:
        """Export audit events in the requested format."""
        self._metrics.export_requested()

        exporter = self._export_registry.get_or_error(format_name)

        if start_date and end_date:
            records = await self._repository.get_events_between(start_date, end_date)
        elif start_date:
            records = await self._repository.get_events_since(start_date)
        else:
            records, _ = await self._repository.get_ordered(limit=100000)

        # Filter by subsystem/event_type if specified
        if subsystem:
            records = [r for r in records if r.get("subsystem") == subsystem]
        if event_type:
            records = [r for r in records if r.get("event_type") == event_type]

        filename, data = exporter.export(records)

        return AuditExportResponse(
            format=format_name,
            event_count=len(records),
            filename=filename,
            size_bytes=len(data),
        )

    async def get_retention_report(self) -> RetentionReport:
        """Get current retention analysis."""
        self._metrics.retention_calculated()
        total = await self._repository.count_events()
        return self._retention.analyze(total)

    async def get_metrics(self) -> dict[str, int]:
        """Get audit metrics."""
        total = await self._repository.count_events()
        snap = self._metrics.snapshot()
        older_than_365 = await self._repository.count_older_than(365)
        return {
            "events_written": total,
            "validation_failures": snap.validation_failures,
            "export_requests": snap.export_requests,
            "hash_failures": snap.hash_failures,
            "retention_calculations": snap.retention_calculations,
            "events_older_than_365_days": older_than_365,
        }

    @staticmethod
    def _to_schema(event: AuditEvent) -> AuditEventSchema:
        return AuditEventSchema(
            audit_id=event.audit_id,
            correlation_id=event.correlation_id,
            timestamp=event.timestamp,
            machine_id=event.machine_id,
            subsystem=event.subsystem,
            actor=event.actor,
            event_type=event.event_type,
            severity=event.severity.value,
            outcome=event.outcome.value,
            description=event.description,
            metadata_json=event.metadata_json,
            current_hash=event.current_hash,
            previous_hash=event.previous_hash,
        )
