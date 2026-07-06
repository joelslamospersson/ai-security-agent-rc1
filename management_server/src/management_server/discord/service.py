"""
Discord registration service — orchestrates guild registration, configuration, and management.
"""

from __future__ import annotations

from typing import Any

import structlog

from management_server.discord.exceptions import (
    GuildAlreadyRegisteredError,
    GuildNotFoundError,
)
from management_server.discord.metrics import DiscordMetricsCollector
from management_server.discord.models import (
    DEFAULT_CATEGORY_NAME,
    DEFAULT_PERMISSION_RULES,
    REQUIRED_CHANNELS,
)
from management_server.discord.repository import DiscordRepository
from management_server.discord.schemas import (
    GuildConfigResponse,
    RegisterGuildRequest,
    RegisterGuildResponse,
    VerifyGuildRequest,
    VerifyGuildResponse,
)
from management_server.discord.validators import DiscordValidator

logger = structlog.get_logger("discord.service")


class DiscordService:
    """Discord Registration Framework service."""

    def __init__(
        self,
        repository: DiscordRepository,
        metrics: DiscordMetricsCollector | None = None,
    ) -> None:
        self._repository = repository
        self._metrics = metrics or DiscordMetricsCollector()

    async def register_guild(self, request: RegisterGuildRequest) -> RegisterGuildResponse:
        """Register a new Discord guild."""
        DiscordValidator.validate_and_raise(request)

        # Check for duplicate
        try:
            existing = await self._repository.get_guild(request.guild_id)
            if existing.get("active"):
                raise GuildAlreadyRegisteredError(request.guild_id)
        except GuildNotFoundError:
            pass  # Expected for new guilds

        # Create the guild record
        await self._repository.create_guild(
            guild_id=request.guild_id,
            name=request.name,
            owner_id=request.owner_id,
        )

        # Associate machine if token was provided
        if request.paired_machine_uuid:
            await self._repository.associate_machine(
                request.guild_id,
                request.paired_machine_uuid,
            )
            self._metrics.machine_associated()

        self._metrics.guild_registered()

        logger.info(
            "Discord guild registered",
            guild_id=request.guild_id,
            name=request.name,
        )

        return RegisterGuildResponse(
            guild_id=request.guild_id,
            name=request.name,
            category_name=DEFAULT_CATEGORY_NAME,
            required_channels=list(REQUIRED_CHANNELS),
            permission_rules=dict(DEFAULT_PERMISSION_RULES),
            message=f"Guild '{request.name}' registered successfully",
        )

    async def verify_guild(self, request: VerifyGuildRequest) -> VerifyGuildResponse:
        """Verify a guild after channels are created."""
        DiscordValidator.validate_guild_id(request.guild_id)

        # Validate channel IDs
        chan_errors = DiscordValidator.validate_channel_ids(request.channel_ids)
        if chan_errors:
            self._metrics.validation_failure()
            return VerifyGuildResponse(
                guild_id=request.guild_id,
                verified=False,
                message="; ".join(chan_errors),
            )

        # Store channel mappings
        for name, cid in request.channel_ids.items():
            await self._repository.set_channel_mapping(request.guild_id, name, cid)

        # Update guild with category and verification
        await self._repository.update_guild(
            request.guild_id,
            category_id=request.category_id,
            verified=True,
        )

        self._metrics.guild_verified()

        logger.info("Discord guild verified", guild_id=request.guild_id)

        return VerifyGuildResponse(
            guild_id=request.guild_id,
            verified=True,
            message="Guild verified and channels configured",
        )

    async def get_guild(self, guild_id: str) -> dict[str, Any]:
        """Get guild information."""
        try:
            guild_record = await self._repository.get_guild(guild_id)
        except GuildNotFoundError:
            raise

        machines = await self._repository.get_machines(guild_id)
        channels = await self._repository.get_channel_mappings(guild_id)

        return {
            "guild_id": guild_record.get("guild_id", ""),
            "name": guild_record.get("name", ""),
            "owner_id": guild_record.get("owner_id", ""),
            "registered_at": guild_record.get("registered_at"),
            "verified": guild_record.get("verified", False),
            "active": guild_record.get("active", True),
            "channel_count": len(channels),
            "machine_count": len(machines),
        }

    async def get_config(self, guild_id: str) -> GuildConfigResponse:
        """Get full configuration for a guild (for Discord Bot consumption)."""
        self._metrics.config_requested()

        try:
            _existing = await self._repository.get_guild(guild_id)
        except GuildNotFoundError:
            raise

        try:
            settings = await self._repository.get_settings(guild_id)
        except GuildNotFoundError:
            settings = {}

        prefs = await self._repository.get_notification_preferences(guild_id)

        import json

        perm_rules = settings.get("permission_rules") or "{}"
        if isinstance(perm_rules, str):
            try:
                perm_rules = json.loads(perm_rules)
            except (json.JSONDecodeError, TypeError):
                perm_rules = dict(DEFAULT_PERMISSION_RULES)
        return GuildConfigResponse(
            guild_id=guild_id,
            category_name=settings.get("category_name", DEFAULT_CATEGORY_NAME),
            required_channels=list(REQUIRED_CHANNELS),
            permission_rules=perm_rules,
            heartbeat_interval_seconds=settings.get("heartbeat_interval_seconds", 30),
            notification_channel=settings.get("notification_channel", "critical-alerts"),
            notification_preferences=[
                {
                    "event_type": p["event_type"],
                    "channel_name": p["channel_name"],
                    "enabled": p["enabled"],
                }
                for p in prefs
            ],
            ping_roles=[],
            maintenance_mode=settings.get("maintenance_mode", False),
        )

    async def delete_guild(self, guild_id: str) -> dict[str, Any]:
        """Delete a guild registration."""
        try:
            await self._repository.get_guild(guild_id)
        except GuildNotFoundError:
            raise

        await self._repository.delete_guild(guild_id)
        self._metrics.guild_deleted()

        logger.info("Discord guild deleted", guild_id=guild_id)

        return {"guild_id": guild_id, "deleted": True, "message": "Guild deleted"}

    async def list_guilds(self) -> list[dict[str, Any]]:
        """List all registered guilds."""
        records, _total = await self._repository.list_guilds()
        return [
            {
                "guild_id": r.get("guild_id", ""),
                "name": r.get("name", ""),
                "owner_id": r.get("owner_id", ""),
                "registered_at": r.get("registered_at"),
                "verified": r.get("verified", False),
                "active": r.get("active", True),
            }
            for r in records
        ]

    async def get_metrics(self) -> dict[str, int]:
        """Get Discord registration metrics."""
        total = await self._repository.get_guild_count()
        snap = self._metrics.snapshot()
        return {
            "guilds_total": total,
            "guilds_registered": snap.guilds_registered,
            "guilds_verified": snap.guilds_verified,
            "guilds_deleted": snap.guilds_deleted,
            "machines_associated": snap.machines_associated,
            "validation_failures": snap.validation_failures,
            "config_requests": snap.config_requests,
        }
