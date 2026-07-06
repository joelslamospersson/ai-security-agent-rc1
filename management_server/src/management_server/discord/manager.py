"""
Discord Manager — high-level facade for the Discord Registration Framework.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.discord.metrics import DiscordMetricsCollector
from management_server.discord.repository import DiscordRepository
from management_server.discord.schemas import (
    GuildConfigResponse,
    RegisterGuildRequest,
    RegisterGuildResponse,
    VerifyGuildRequest,
    VerifyGuildResponse,
)
from management_server.discord.service import DiscordService

logger = structlog.get_logger("discord.manager")


class DiscordManager:
    """High-level facade for the Discord Registration Framework."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = DiscordRepository(session)
        self._metrics = DiscordMetricsCollector()
        self._service = DiscordService(repository=self._repository, metrics=self._metrics)
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("Discord manager initialized")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def service(self) -> DiscordService:
        return self._service

    async def register_guild(self, request: RegisterGuildRequest) -> RegisterGuildResponse:
        return await self._service.register_guild(request)

    async def verify_guild(self, request: VerifyGuildRequest) -> VerifyGuildResponse:
        return await self._service.verify_guild(request)

    async def get_guild(self, guild_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._service.get_guild(guild_id)
        return result

    async def get_config(self, guild_id: str) -> GuildConfigResponse:
        return await self._service.get_config(guild_id)

    async def delete_guild(self, guild_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._service.delete_guild(guild_id)
        return result

    async def list_guilds(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._service.list_guilds()
        return result

    async def get_metrics(self) -> dict[str, int]:
        result: dict[str, int] = await self._service.get_metrics()
        return result
