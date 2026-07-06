"""
Discord Registration API endpoints.

POST   /api/v1/discord/register          — Register a guild
POST   /api/v1/discord/verify             — Verify a guild
GET    /api/v1/discord/guild/{guild_id}    — Get guild info
GET    /api/v1/discord/config/{guild_id}   — Get guild config
DELETE /api/v1/discord/guild/{guild_id}    — Delete a guild
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from management_server.discord.exceptions import (
    GuildAlreadyRegisteredError,
    GuildNotFoundError,
    ValidationError,
)
from management_server.discord.manager import DiscordManager
from management_server.discord.schemas import (
    ErrorResponse,
    GuildConfigResponse,
    GuildDeleteResponse,
    GuildInfo,
    RegisterGuildRequest,
    RegisterGuildResponse,
    VerifyGuildRequest,
    VerifyGuildResponse,
)

router = APIRouter(prefix="/api/v1/discord", tags=["discord"])


async def _get_discord_manager(request: Request) -> DiscordManager:
    mgr: DiscordManager | None = getattr(request.app.state, "discord_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Discord manager not initialized")
    return mgr


@router.post(
    "/register",
    response_model=RegisterGuildResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="Register a Discord guild",
)
async def register_guild(
    body: RegisterGuildRequest,
    manager: DiscordManager = Depends(_get_discord_manager),  # noqa: B008
) -> RegisterGuildResponse:
    """Register a new Discord guild and return its configuration."""
    try:
        return await manager.register_guild(body)
    except GuildAlreadyRegisteredError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/verify",
    response_model=VerifyGuildResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Verify a guild registration",
)
async def verify_guild(
    body: VerifyGuildRequest,
    manager: DiscordManager = Depends(_get_discord_manager),  # noqa: B008
) -> VerifyGuildResponse:
    """Verify a guild after channels have been created."""
    return await manager.verify_guild(body)


@router.get(
    "/guild/{guild_id}",
    response_model=GuildInfo,
    responses={404: {"model": ErrorResponse}},
    summary="Get guild information",
)
async def get_guild(
    guild_id: str,
    manager: DiscordManager = Depends(_get_discord_manager),  # noqa: B008
) -> dict[str, Any]:
    """Get information about a registered Discord guild."""
    try:
        guild_result: dict[str, Any] = await manager.get_guild(guild_id)
        return guild_result
    except GuildNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get(
    "/config/{guild_id}",
    response_model=GuildConfigResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get guild configuration",
)
async def get_guild_config(
    guild_id: str,
    manager: DiscordManager = Depends(_get_discord_manager),  # noqa: B008
) -> GuildConfigResponse:
    """Get full configuration for a Discord guild (for bot consumption)."""
    try:
        return await manager.get_config(guild_id)
    except GuildNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete(
    "/guild/{guild_id}",
    response_model=GuildDeleteResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Delete a guild registration",
)
async def delete_guild(
    guild_id: str,
    manager: DiscordManager = Depends(_get_discord_manager),  # noqa: B008
) -> dict[str, Any]:
    """Delete a guild registration and all associated data."""
    try:
        delete_result: dict[str, Any] = await manager.delete_guild(guild_id)
        return delete_result
    except GuildNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
