"""
Heartbeat API endpoints for the Management Server.

POST /api/v1/heartbeat                — Submit a heartbeat
GET  /api/v1/heartbeat/status/{id}    — Get machine status
GET  /api/v1/heartbeat/metrics        — Get heartbeat metrics

Authentication is isolated behind interfaces for later implementation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from management_server.heartbeat.exceptions import (
    HeartbeatError,
    HeartbeatValidationError,
    MachineNotRegisteredError,
    ProtocolMismatchError,
    SequenceReplayError,
)
from management_server.heartbeat.manager import HeartbeatManager
from management_server.heartbeat.schemas import (
    ErrorResponse,
    HeartbeatMetricsSchema,
    HeartbeatRequestSchema,
    HeartbeatResponseSchema,
    MachineStatusSchema,
)

router = APIRouter(prefix="/api/v1", tags=["heartbeat"])


async def _get_heartbeat_manager(request: Request) -> HeartbeatManager:
    """Dependency: get the heartbeat manager from app state.

    Authentication boundary — wrap with auth middleware later.
    """
    mgr: HeartbeatManager | None = getattr(request.app.state, "heartbeat_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Heartbeat manager not initialized")
    return mgr


@router.post(
    "/heartbeat",
    response_model=HeartbeatResponseSchema,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Submit a heartbeat",
)
async def submit_heartbeat(
    body: HeartbeatRequestSchema,
    manager: HeartbeatManager = Depends(_get_heartbeat_manager),  # noqa: B008
) -> HeartbeatResponseSchema:
    """Submit a heartbeat from an AI Security Agent.

    Validates the heartbeat, records it, negotiates protocol version,
    and returns server state.
    """
    try:
        return await manager.process_heartbeat(body, is_registered=True)
    except HeartbeatValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except MachineNotRegisteredError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except (ProtocolMismatchError, SequenceReplayError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HeartbeatError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/heartbeat/status/{machine_uuid}",
    response_model=MachineStatusSchema,
    responses={404: {"model": ErrorResponse}},
    summary="Get machine status",
)
async def get_machine_status(
    machine_uuid: str,
    manager: HeartbeatManager = Depends(_get_heartbeat_manager),  # noqa: B008
) -> MachineStatusSchema:
    """Get the current online status of a machine."""
    return await manager.get_machine_status(machine_uuid)


@router.get(
    "/heartbeat/metrics",
    response_model=HeartbeatMetricsSchema,
    summary="Get heartbeat metrics",
)
async def get_heartbeat_metrics(
    manager: HeartbeatManager = Depends(_get_heartbeat_manager),  # noqa: B008
) -> HeartbeatMetricsSchema:
    """Get heartbeat system metrics."""
    return await manager.get_metrics()
