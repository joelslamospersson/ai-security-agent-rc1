"""
Registration API endpoints for the Management Server.

POST   /api/v1/registration              — Create registration request
GET    /api/v1/registration/{id}         — Lookup registration
POST   /api/v1/registration/{id}/approve — Approve registration
POST   /api/v1/registration/{id}/reject  — Reject registration

Authentication is isolated behind interfaces for later implementation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from management_server.machines.exceptions import (
    ApprovalError,
    DuplicateMachineError,
    InvalidTransitionError,
    MachineNotFoundError,
    RegistrationError,
)
from management_server.machines.manager import MachineManager
from management_server.machines.schemas import (
    ApprovalRequest,
    ErrorResponse,
    RegistrationRequest,
    RegistrationResponse,
    RejectionRequest,
)

router = APIRouter(prefix="/api/v1", tags=["registration"])


async def _get_machine_manager(request: Request) -> MachineManager:
    """Dependency: get the machine manager from app state.

    Authentication boundary — wrap this with auth middleware later.
    """
    mgr: MachineManager | None = getattr(request.app.state, "machine_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Machine manager not initialized")
    return mgr


@router.post(
    "/registration",
    response_model=RegistrationResponse,
    responses={409: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
    summary="Create registration request",
)
async def create_registration(
    body: RegistrationRequest,
    manager: MachineManager = Depends(_get_machine_manager),  # noqa: B008
) -> RegistrationResponse:
    """Register a new machine. Returns pending status."""
    try:
        return await manager.create_registration(body)
    except DuplicateMachineError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except RegistrationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/registration/{machine_uuid}",
    responses={404: {"model": ErrorResponse}},
    summary="Lookup registration",
)
async def get_registration(
    machine_uuid: str,
    manager: MachineManager = Depends(_get_machine_manager),  # noqa: B008
) -> dict[str, object]:
    """Get machine registration details."""
    try:
        return await manager.lookup(machine_uuid)  # type: ignore[no-any-return]
    except MachineNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post(
    "/registration/{machine_uuid}/approve",
    response_model=RegistrationResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Approve registration",
)
async def approve_registration(
    machine_uuid: str,
    body: ApprovalRequest,
    manager: MachineManager = Depends(_get_machine_manager),  # noqa: B008
) -> RegistrationResponse:
    """Approve a pending registration and issue a certificate."""
    try:
        return await manager.approve(
            machine_uuid=machine_uuid,
            approved_by=body.approved_by,
            reason=body.reason,
        )
    except MachineNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (ApprovalError, InvalidTransitionError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/registration/{machine_uuid}/reject",
    response_model=RegistrationResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Reject registration",
)
async def reject_registration(
    machine_uuid: str,
    body: RejectionRequest,
    manager: MachineManager = Depends(_get_machine_manager),  # noqa: B008
) -> RegistrationResponse:
    """Reject a pending registration."""
    try:
        return await manager.reject(
            machine_uuid=machine_uuid,
            rejected_by=body.rejected_by,
            reason=body.reason,
        )
    except MachineNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
