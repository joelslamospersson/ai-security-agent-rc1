"""
Commands API endpoints for the Management Server.

GET    /api/v1/commands                        — List commands
GET    /api/v1/commands/{command_id}           — Get command
POST   /api/v1/commands                       — Create command
POST   /api/v1/commands/{command_id}/cancel    — Cancel command
POST   /api/v1/commands/{command_id}/authorize — Authorize command
GET    /api/v1/commands/machine/{machine_id}   — Get pending for machine
GET    /api/v1/commands/types                  — List supported types
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from management_server.commands.exceptions import (
    AuthorizationError,
    CommandNotFoundError,
    CommandValidationError,
    InvalidTransitionError,
    UnsupportedCommandTypeError,
)
from management_server.commands.manager import CommandManager
from management_server.commands.schemas import (
    AuthorizeCommandRequest,
    CancelCommandRequest,
    CommandSchema,
    CommandTypeInfo,
    CreateCommandRequest,
    ErrorResponse,
)

router = APIRouter(prefix="/api/v1", tags=["commands"])


async def _get_command_manager(request: Request) -> CommandManager:
    mgr: CommandManager | None = getattr(request.app.state, "command_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Command manager not initialized")
    return mgr


@router.get(
    "/commands",
    summary="List commands",
)
async def list_commands(
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    machine_id: str | None = Query(default=None),
    state: str | None = Query(default=None),
    manager: CommandManager = Depends(_get_command_manager),  # noqa: B008
) -> dict[str, Any]:
    """List remote commands with optional filters."""
    result: dict[str, Any] = await manager.list_commands(
        limit=limit,
        offset=offset,
        machine_id=machine_id,
        state=state,
    )
    return result


@router.get(
    "/commands/{command_id}",
    response_model=CommandSchema,
    responses={404: {"model": ErrorResponse}},
    summary="Get a command",
)
async def get_command(
    command_id: str,
    manager: CommandManager = Depends(_get_command_manager),  # noqa: B008
) -> CommandSchema:
    """Get a specific command by ID."""
    command = await manager.get_command(command_id)
    if command is None:
        raise HTTPException(status_code=404, detail=f"Command not found: {command_id}")
    return command


@router.post(
    "/commands",
    response_model=CommandSchema,
    responses={400: {"model": ErrorResponse}},
    summary="Create a command",
)
async def create_command(
    body: CreateCommandRequest,
    manager: CommandManager = Depends(_get_command_manager),  # noqa: B008
) -> CommandSchema:
    """Create a new remote command."""
    try:
        return await manager.create_command(body)
    except (CommandValidationError, UnsupportedCommandTypeError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/commands/{command_id}/cancel",
    response_model=CommandSchema,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Cancel a command",
)
async def cancel_command(
    command_id: str,
    body: CancelCommandRequest,
    manager: CommandManager = Depends(_get_command_manager),  # noqa: B008
) -> CommandSchema:
    """Cancel a pending command."""
    try:
        return await manager.cancel_command(
            command_id,
            cancelled_by=body.cancelled_by,
            reason=body.reason,
        )
    except CommandNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/commands/{command_id}/authorize",
    response_model=CommandSchema,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Authorize a command",
)
async def authorize_command(
    command_id: str,
    body: AuthorizeCommandRequest,
    manager: CommandManager = Depends(_get_command_manager),  # noqa: B008
) -> CommandSchema:
    """Authorize a queued command for delivery."""
    try:
        return await manager.authorize_command(
            command_id,
            authorized_by=body.authorized_by,
            reason=body.reason,
        )
    except CommandNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (InvalidTransitionError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/commands/machine/{machine_id}",
    summary="Get pending commands for machine",
)
async def get_pending_commands(
    machine_id: str,
    manager: CommandManager = Depends(_get_command_manager),  # noqa: B008
) -> list[dict[str, Any]]:
    """Get pending commands for a machine (heartbeat delivery)."""
    result: list[dict[str, Any]] = await manager.get_pending_for_machine(machine_id)
    return result


@router.get(
    "/commands/types",
    response_model=list[CommandTypeInfo],
    summary="List supported command types",
)
async def list_command_types(
    manager: CommandManager = Depends(_get_command_manager),  # noqa: B008
) -> list[CommandTypeInfo]:
    """Get all supported command types with parameter schemas."""
    result_list: list[CommandTypeInfo] = await manager.get_supported_types()
    return result_list
