"""
Command Manager — high-level facade for the Remote Command Framework.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.commands.authorization import CommandAuthorizer
from management_server.commands.metrics import CommandMetricsCollector
from management_server.commands.queue import CommandQueue
from management_server.commands.repository import CommandRepository
from management_server.commands.schemas import (
    CommandSchema,
    CommandTypeInfo,
    CreateCommandRequest,
)
from management_server.commands.service import CommandService

logger = structlog.get_logger("commands.manager")


class CommandManager:
    """High-level facade for the Remote Command Framework."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = CommandRepository(session)
        self._queue = CommandQueue()
        self._authorizer = CommandAuthorizer()
        self._metrics = CommandMetricsCollector()
        self._service = CommandService(
            repository=self._repository,
            queue=self._queue,
            authorizer=self._authorizer,
            metrics=self._metrics,
        )
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("Command manager initialized")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def service(self) -> CommandService:
        return self._service

    async def create_command(self, request: CreateCommandRequest) -> CommandSchema:
        return await self._service.create_command(request)

    async def get_command(self, command_id: str) -> CommandSchema | None:
        return await self._service.get_command(command_id)

    async def list_commands(
        self,
        limit: int = 100,
        offset: int = 0,
        machine_id: str | None = None,
        state: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = await self._service.list_commands(
            limit=limit,
            offset=offset,
            machine_id=machine_id,
            state=state,
        )
        return result

    async def authorize_command(
        self, command_id: str, authorized_by: str = "admin", reason: str = ""
    ) -> CommandSchema:
        return await self._service.authorize_command(command_id, authorized_by, reason)

    async def cancel_command(
        self, command_id: str, cancelled_by: str = "admin", reason: str = ""
    ) -> CommandSchema:
        return await self._service.cancel_command(command_id, cancelled_by, reason)

    async def get_pending_for_machine(self, machine_id: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._service.get_pending_for_machine(machine_id)
        return result

    async def get_supported_types(self) -> list[CommandTypeInfo]:
        result: list[CommandTypeInfo] = await self._service.get_supported_types()
        return result

    async def get_lifecycle(self, command_id: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._service.get_lifecycle(command_id)
        return result

    async def get_metrics(self) -> dict[str, int | float]:
        result: dict[str, int | float] = await self._service.get_metrics()
        return result
