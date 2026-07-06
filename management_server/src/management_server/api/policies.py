"""
Policy API endpoints for the Management Server.

GET    /api/v1/policies                  — List policies
GET    /api/v1/policies/{name}           — Get policy
POST   /api/v1/policies/validate         — Validate YAML
POST   /api/v1/policies/{name}/assign/{machine_uuid}  — Assign policy
POST   /api/v1/policies/{name}/override/{machine_uuid} — Override policy value

Authentication is isolated behind interfaces for later implementation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from management_server.policies.exceptions import (
    AssignmentError,
    OverrideError,
    PolicyError,
    PolicyNotFoundError,
)
from management_server.policies.manager import PolicyManager
from management_server.policies.schemas import (
    ErrorResponse,
    PolicyAssignRequest,
    PolicyOverrideRequest,
    PolicySchema,
    PolicyValidateRequest,
    PolicyValidateResponse,
)

router = APIRouter(prefix="/api/v1", tags=["policies"])


async def _get_policy_manager(request: Request) -> PolicyManager:
    mgr: PolicyManager | None = getattr(request.app.state, "policy_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Policy manager not initialized")
    return mgr


@router.get(
    "/policies",
    response_model=list[PolicySchema],
    summary="List all policies",
)
async def list_policies(
    manager: PolicyManager = Depends(_get_policy_manager),  # noqa: B008
) -> list[PolicySchema]:
    """Get all loaded policies."""
    result_list: list[PolicySchema] = await manager.list_policies()
    return result_list


@router.get(
    "/policies/{name}",
    response_model=PolicySchema,
    responses={404: {"model": ErrorResponse}},
    summary="Get a policy",
)
async def get_policy(
    name: str,
    manager: PolicyManager = Depends(_get_policy_manager),  # noqa: B008
) -> PolicySchema:
    """Get a policy by name with inheritance resolved."""
    try:
        return await manager.get_policy(name)
    except (PolicyError, PolicyNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post(
    "/policies/validate",
    response_model=PolicyValidateResponse,
    summary="Validate a policy YAML",
)
async def validate_policy(
    body: PolicyValidateRequest,
    manager: PolicyManager = Depends(_get_policy_manager),  # noqa: B008
) -> PolicyValidateResponse:
    """Validate a YAML policy string without loading it."""
    return await manager.validate_policy_yaml(body.name, body.yaml_content)


@router.post(
    "/policies/{name}/assign/{machine_uuid}",
    responses={404: {"model": ErrorResponse}},
    summary="Assign a policy to a machine",
)
async def assign_policy(
    name: str,
    machine_uuid: str,
    body: PolicyAssignRequest,
    manager: PolicyManager = Depends(_get_policy_manager),  # noqa: B008
) -> dict[str, object]:
    """Assign a policy to a machine."""
    try:
        result_assign: dict[str, object] = await manager.assign_policy_named(
            machine_uuid=machine_uuid,
            policy_name=name,
            assigned_by=body.assigned_by,
        )
        return result_assign
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AssignmentError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/policies/{name}/override/{machine_uuid}",
    responses={404: {"model": ErrorResponse}},
    summary="Override a policy value for a machine",
)
async def override_policy(
    _name: str,
    _machine_uuid: str,
    body: PolicyOverrideRequest,
    manager: PolicyManager = Depends(_get_policy_manager),  # noqa: B008
) -> dict[str, object]:
    """Override a policy value for a specific machine."""
    try:
        override_result: dict[str, object] = await manager.set_override(body)
        return override_result
    except (PolicyNotFoundError, OverrideError, AssignmentError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
