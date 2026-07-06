"""
Routing Manager — high-level facade for the Routing Engine.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.routing.matcher import RoutingMatcher
from management_server.routing.metrics import RoutingMetricsCollector
from management_server.routing.repository import RoutingRepository
from management_server.routing.schemas import (
    EventToRoute,
    RoutingConfigReloadResponse,
    RoutingDecisionSchema,
    RoutingEvaluateResponse,
    RoutingRuleSchema,
)
from management_server.routing.service import RoutingService

logger = structlog.get_logger("routing.manager")


class RoutingManager:
    """High-level facade for the Routing Engine."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = RoutingRepository(session)
        self._matcher = RoutingMatcher([])
        self._metrics = RoutingMetricsCollector()
        self._service = RoutingService(
            repository=self._repository,
            matcher=self._matcher,
            metrics=self._metrics,
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the routing manager: load configuration."""
        result = await self._service.load_config()
        logger.info(
            "Routing manager initialized",
            rules=result.rules_loaded,
            errors=len(result.errors),
        )
        self._initialized = True

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def service(self) -> RoutingService:
        return self._service

    async def evaluate(self, event: EventToRoute) -> RoutingEvaluateResponse:
        return await self._service.evaluate(event)

    async def get_decision(self, decision_id: str) -> RoutingDecisionSchema | None:
        return await self._service.get_decision(decision_id)

    async def list_decisions(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        result: dict[str, Any] = await self._service.list_decisions(limit, offset)
        return result

    async def list_rules(self) -> list[RoutingRuleSchema]:
        result: list[RoutingRuleSchema] = await self._service.list_rules()
        return result

    async def reload_config(self) -> RoutingConfigReloadResponse:
        return await self._service.load_config()

    async def get_metrics(self) -> dict[str, int | float]:
        result: dict[str, int | float] = await self._service.get_metrics()
        return result
