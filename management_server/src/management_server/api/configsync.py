"""
Config sync API endpoints.

GET    /api/v1/packages                       — List packages
GET    /api/v1/packages/{package_id}          — Get package
POST   /api/v1/packages                      — Create package
POST   /api/v1/packages/publish              — Publish package
GET    /api/v1/packages/available/{machine_id} — Get available for heartbeat
GET    /api/v1/packages/machine/{machine_id}   — Get machine versions
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from management_server.configsync.exceptions import (
    ConfigSyncError,
    PackageNotFoundError,
    PackageValidationError,
)
from management_server.configsync.manager import ConfigSyncManager
from management_server.configsync.schemas import (
    AvailablePackageSchema,
    CreatePackageRequest,
    ErrorResponse,
    PackageSchema,
    PublishRequest,
)

router = APIRouter(prefix="/api/v1", tags=["configsync"])


async def _get_configsync_manager(request: Request) -> ConfigSyncManager:
    mgr: ConfigSyncManager | None = getattr(request.app.state, "configsync_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Config sync manager not initialized")
    return mgr


@router.get("/packages", summary="List packages")
async def list_packages(
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    package_type: str | None = Query(default=None),
    state: str | None = Query(default=None),
    manager: ConfigSyncManager = Depends(_get_configsync_manager),  # noqa: B008
) -> dict[str, Any]:
    """List configuration packages with optional filters."""
    result: dict[str, Any] = await manager.list_packages(
        limit=limit,
        offset=offset,
        package_type=package_type,
        state=state,
    )
    return result


@router.get(
    "/packages/{package_id}",
    response_model=PackageSchema,
    responses={404: {"model": ErrorResponse}},
    summary="Get a package",
)
async def get_package(
    package_id: str,
    manager: ConfigSyncManager = Depends(_get_configsync_manager),  # noqa: B008
) -> PackageSchema:
    pkg = await manager.get_package(package_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail=f"Package not found: {package_id}")
    return pkg


@router.post(
    "/packages",
    response_model=PackageSchema,
    responses={400: {"model": ErrorResponse}},
    summary="Create a package",
)
async def create_package(
    body: CreatePackageRequest,
    manager: ConfigSyncManager = Depends(_get_configsync_manager),  # noqa: B008
) -> PackageSchema:
    try:
        return await manager.create_package(body)
    except PackageValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/packages/publish",
    response_model=PackageSchema,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Publish a package",
)
async def publish_package(
    body: PublishRequest,
    manager: ConfigSyncManager = Depends(_get_configsync_manager),  # noqa: B008
) -> PackageSchema:
    try:
        return await manager.publish_package(body.package_id, body.published_by)
    except PackageNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConfigSyncError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/packages/available/{machine_uuid}",
    response_model=list[AvailablePackageSchema],
    summary="Get available packages for machine",
)
async def get_available_packages(
    machine_uuid: str,
    agent_version: str = Query(default=""),
    manager: ConfigSyncManager = Depends(_get_configsync_manager),  # noqa: B008
) -> list[AvailablePackageSchema]:
    """Get available packages for a machine (heartbeat advertisement)."""
    result: list[AvailablePackageSchema] = await manager.get_available_for_heartbeat(
        machine_uuid,
        agent_version,
    )
    return result


@router.get(
    "/packages/machine/{machine_uuid}",
    summary="Get machine package versions",
)
async def get_machine_versions(
    machine_uuid: str,
    manager: ConfigSyncManager = Depends(_get_configsync_manager),  # noqa: B008
) -> list[dict[str, Any]]:
    """Get version state for a machine."""
    result: list[dict[str, Any]] = await manager.get_machine_versions(machine_uuid)
    return result
