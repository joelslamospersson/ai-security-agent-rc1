"""
Pairing Manager — high-level facade for the pairing subsystem.

Coordinates repository, service, generator, validator, and metrics.
Provides a single entry point for API handlers and app initialization.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.machines.service import RegistrationService
from management_server.pairing.generator import PairingTokenGenerator
from management_server.pairing.metrics import PairingMetricsCollector
from management_server.pairing.repository import PairingRepository
from management_server.pairing.schemas import (
    PairingConsumeRequest,
    PairingConsumeResponse,
    PairingTokenCreateRequest,
    PairingTokenResponse,
    PairingValidateRequest,
    PairingValidateResponse,
)
from management_server.pairing.service import PairingService

logger = structlog.get_logger("pairing.manager")


class PairingManager:
    """High-level facade for the pairing subsystem."""

    def __init__(
        self,
        session: AsyncSession,
        registration_service: RegistrationService | None = None,
    ) -> None:
        self._session = session
        self._repository = PairingRepository(session)
        self._generator = PairingTokenGenerator()
        self._metrics = PairingMetricsCollector()
        self._service = PairingService(
            repository=self._repository,
            generator=self._generator,
            metrics=self._metrics,
            registration_service=registration_service,
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the pairing manager."""
        self._initialized = True
        logger.info("Pairing manager initialized")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def service(self) -> PairingService:
        return self._service

    async def create_token(self, request: PairingTokenCreateRequest) -> PairingTokenResponse:
        return await self._service.create_token(request)

    async def validate_token(self, request: PairingValidateRequest) -> PairingValidateResponse:
        return await self._service.validate_token(request)

    async def consume_token(self, request: PairingConsumeRequest) -> PairingConsumeResponse:
        return await self._service.consume_token(request)

    async def get_token_info(self, token_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._service.get_token_info(token_id)
        return result

    async def revoke_token(self, token_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._service.revoke_token(token_id)
        return result

    async def list_tokens(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        result: dict[str, Any] = await self._service.list_tokens(
            status=status, limit=limit, offset=offset
        )
        return result

    async def get_metrics(self) -> dict[str, int]:
        result: dict[str, int] = await self._service.get_metrics()
        return result

    async def expire_stale_tokens(self) -> int:
        result: int = await self._service.expire_stale_tokens()
        return result
