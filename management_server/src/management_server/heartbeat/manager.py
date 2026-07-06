"""
Heartbeat Manager — high-level facade for the heartbeat subsystem.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.heartbeat.metrics import HeartbeatMetricsCollector
from management_server.heartbeat.models import TimeoutConfig
from management_server.heartbeat.protocol import HeartbeatProtocol
from management_server.heartbeat.repository import HeartbeatRepository
from management_server.heartbeat.schemas import (
    HeartbeatMetricsSchema,
    HeartbeatRequestSchema,
    HeartbeatResponseSchema,
    MachineStatusSchema,
)
from management_server.heartbeat.service import HeartbeatService

logger = structlog.get_logger("heartbeat.manager")


class HeartbeatManager:
    """High-level facade for the heartbeat subsystem."""

    def __init__(
        self,
        session: AsyncSession,
        timeout_config: TimeoutConfig | None = None,
    ) -> None:
        self._session = session
        self._repository = HeartbeatRepository(session)
        self._protocol = HeartbeatProtocol()
        self._metrics = HeartbeatMetricsCollector()
        self._service = HeartbeatService(
            repository=self._repository,
            protocol=self._protocol,
            metrics=self._metrics,
            timeout_config=timeout_config or TimeoutConfig(),
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the heartbeat manager."""
        self._initialized = True
        logger.info("Heartbeat manager initialized")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def service(self) -> HeartbeatService:
        return self._service

    async def process_heartbeat(
        self, schema: HeartbeatRequestSchema, is_registered: bool = True
    ) -> HeartbeatResponseSchema:
        return await self._service.process_heartbeat(schema, is_registered)

    async def detect_timeouts(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._service.detect_timeouts()
        return result

    async def get_machine_status(self, machine_uuid: str) -> MachineStatusSchema:
        return await self._service.get_machine_status(machine_uuid)

    async def get_metrics(self) -> HeartbeatMetricsSchema:
        return await self._service.get_metrics()

    async def get_all_statuses(self) -> list[MachineStatusSchema]:
        from management_server.heartbeat.models import MachineStatus

        results: list[MachineStatusSchema] = []
        for status in MachineStatus:
            machines = await self._repository.get_machines_by_status(status)
            for record in machines:
                results.append(
                    MachineStatusSchema(
                        machine_uuid=record.get("machine_uuid", ""),
                        status=record.get("status", status.value),
                        hostname=record.get("hostname", ""),
                        protocol_version=record.get("protocol_version", ""),
                        agent_version=record.get("agent_version", ""),
                        last_heartbeat=record.get("last_heartbeat_at"),
                        environment=record.get("environment", ""),
                    )
                )
        return results
