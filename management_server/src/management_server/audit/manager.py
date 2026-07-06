"""
Audit Manager — high-level facade for the Audit Engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.audit.exporter import ExportRegistry
from management_server.audit.metrics import AuditMetricsCollector
from management_server.audit.models import AuditOutcome, AuditSeverity
from management_server.audit.repository import AuditRepository
from management_server.audit.retention import RetentionCalculator, RetentionReport
from management_server.audit.schemas import (
    AuditEventSchema,
    AuditExportResponse,
    AuditVerifyResponse,
)
from management_server.audit.service import AuditService

logger = structlog.get_logger("audit.manager")


class AuditManager:
    """High-level facade for the Audit Engine."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = AuditRepository(session)
        self._retention = RetentionCalculator()
        self._export_registry = ExportRegistry()
        self._metrics = AuditMetricsCollector()
        self._service = AuditService(
            repository=self._repository,
            retention_calculator=self._retention,
            export_registry=self._export_registry,
            metrics=self._metrics,
        )
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("Audit manager initialized")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def service(self) -> AuditService:
        return self._service

    async def record(
        self,
        subsystem: str,
        event_type: str,
        description: str = "",
        machine_id: str = "",
        actor: str = "system",
        severity: str = "info",
        outcome: str = "success",
        correlation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEventSchema:
        return await self._service.record(
            subsystem=subsystem,
            event_type=event_type,
            description=description,
            machine_id=machine_id,
            actor=actor,
            severity=AuditSeverity(severity),
            outcome=AuditOutcome(outcome),
            correlation_id=correlation_id,
            metadata=metadata,
        )

    async def get_event(self, audit_id: str) -> AuditEventSchema | None:
        return await self._service.get_event(audit_id)

    async def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        subsystem: str | None = None,
        event_type: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = await self._service.list_events(
            limit=limit,
            offset=offset,
            subsystem=subsystem,
            event_type=event_type,
        )
        return result

    async def verify_integrity(self) -> AuditVerifyResponse:
        return await self._service.verify_integrity()

    async def export_events(
        self,
        format_name: str = "json",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        subsystem: str | None = None,
        event_type: str | None = None,
    ) -> AuditExportResponse:
        return await self._service.export_events(
            format_name=format_name,
            start_date=start_date,
            end_date=end_date,
            subsystem=subsystem,
            event_type=event_type,
        )

    async def get_retention_report(self) -> RetentionReport:
        return await self._service.get_retention_report()

    async def get_metrics(self) -> dict[str, int]:
        result: dict[str, int] = await self._service.get_metrics()
        return result
