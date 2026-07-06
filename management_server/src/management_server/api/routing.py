"""
Routing API endpoints for the Management Server.

GET    /api/v1/routing                — List routing rules
POST   /api/v1/routing/evaluate       — Evaluate an event
POST   /api/v1/routing/reload         — Reload routing config
GET    /api/v1/routing/decisions      — List decisions
GET    /api/v1/routing/decisions/{id} — Get a decision
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from management_server.routing.manager import RoutingManager
from management_server.routing.schemas import (
    ErrorResponse,
    EventToRoute,
    RoutingConfigReloadResponse,
    RoutingDecisionSchema,
    RoutingEvaluateResponse,
    RoutingRuleSchema,
)

router = APIRouter(prefix="/api/v1", tags=["routing"])


async def _get_routing_manager(request: Request) -> RoutingManager:
    mgr: RoutingManager | None = getattr(request.app.state, "routing_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Routing manager not initialized")
    return mgr


@router.get(
    "/routing",
    response_model=list[RoutingRuleSchema],
    summary="List routing rules",
)
async def list_routing_rules(
    manager: RoutingManager = Depends(_get_routing_manager),  # noqa: B008
) -> list[RoutingRuleSchema]:
    """Get all loaded routing rules."""
    result_list: list[Any] = await manager.list_rules()
    return result_list


@router.post(
    "/routing/evaluate",
    response_model=RoutingEvaluateResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Evaluate an event",
)
async def evaluate_event(
    body: EventToRoute,
    manager: RoutingManager = Depends(_get_routing_manager),  # noqa: B008
) -> RoutingEvaluateResponse:
    """Evaluate an event against routing rules and produce a decision."""
    return await manager.evaluate(body)


@router.post(
    "/routing/reload",
    response_model=RoutingConfigReloadResponse,
    summary="Reload routing configuration",
)
async def reload_routing_config(
    manager: RoutingManager = Depends(_get_routing_manager),  # noqa: B008
) -> RoutingConfigReloadResponse:
    """Reload routing rules from YAML configuration."""
    return await manager.reload_config()


@router.get(
    "/routing/decisions",
    summary="List routing decisions",
)
async def list_routing_decisions(
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    manager: RoutingManager = Depends(_get_routing_manager),  # noqa: B008
) -> dict[str, Any]:
    """List recent routing decisions."""
    result_dict: dict[str, Any] = await manager.list_decisions(limit=limit, offset=offset)
    return result_dict


@router.get(
    "/routing/decisions/{decision_id}",
    response_model=RoutingDecisionSchema,
    responses={404: {"model": ErrorResponse}},
    summary="Get a routing decision",
)
async def get_routing_decision(
    decision_id: str,
    manager: RoutingManager = Depends(_get_routing_manager),  # noqa: B008
) -> RoutingDecisionSchema:
    """Get a specific routing decision by ID."""
    decision = await manager.get_decision(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail=f"Decision not found: {decision_id}")
    return decision
