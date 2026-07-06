"""
Guild manager — guild registration, channel creation, and synchronization.

Automatically creates and maintains the Discord channel structure.
"""

from __future__ import annotations

from typing import Any

import discord
import structlog

from discord_bot.exceptions import ChannelCreationError, GuildRegistrationError

logger = structlog.get_logger("discord_bot.guild_manager")

CHANNEL_STRUCTURE: list[dict[str, Any]] = [
    {"name": "bot-status", "type": "text", "description": "Bot status and health"},
    {"name": "critical-alerts", "type": "text", "description": "Critical security alerts"},
    {"name": "detections", "type": "text", "description": "Security detections log"},
    {"name": "monitored-addresses", "type": "text", "description": "Monitored IPs and addresses"},
    {"name": "quarantine", "type": "text", "description": "Quarantine notifications"},
    {"name": "audit-log", "type": "text", "description": "Immutable audit log"},
    {"name": "security-reports", "type": "text", "description": "Periodic security reports"},
    {"name": "pairing-log", "type": "text", "description": "Machine pairing events"},
    {"name": "system-events", "type": "text", "description": "System-level events"},
]

CATEGORY_NAME = "AI Security"


class GuildManager:
    """Manages Discord guild registration and channel synchronization.

    Communicates with the Management Server API for registration.
    Uses discord.py for channel management.
    """

    def __init__(self) -> None:
        self._registered_guilds: dict[str, dict[str, Any]] = {}

    async def register_guild(
        self,
        guild_id: str,
        guild_name: str,
        api_client: Any,
    ) -> dict[str, Any]:
        """Register a guild with the Management Server."""
        try:
            result = await api_client.register_guild(guild_id, guild_name)
            self._registered_guilds[guild_id] = {
                "id": guild_id,
                "name": guild_name,
                "registered_at": result.get("registered_at", ""),
            }
            logger.info("Guild registered", guild_id=guild_id, name=guild_name)
            return self._registered_guilds[guild_id]
        except Exception as e:
            raise GuildRegistrationError(f"Failed to register guild {guild_id}: {e}") from e

    async def ensure_category(self, guild: Any) -> Any:
        """Ensure the AI Security category exists, creating it if missing."""
        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(CATEGORY_NAME)
            logger.info("Category created", guild=guild.name, category=CATEGORY_NAME)
        return category

    async def ensure_channels(self, guild: Any, category: Any) -> list[Any]:
        """Ensure all required channels exist under the category."""
        existing_channels = {c.name: c for c in category.channels}
        created: list[Any] = []

        for chan_def in CHANNEL_STRUCTURE:
            name = chan_def["name"]
            if name in existing_channels:
                continue
            try:
                channel = await guild.create_text_channel(name, category=category)
                created.append(channel)
                logger.info("Channel created", guild=guild.name, channel=name)
            except Exception as e:
                raise ChannelCreationError(name, str(e)) from e

        return created

    async def synchronize(self, guild: Any) -> dict[str, Any]:
        """Full synchronization: ensure category + all channels exist."""
        category = await self.ensure_category(guild)
        created = await self.ensure_channels(guild, category)
        return {
            "guild": guild.name,
            "category": CATEGORY_NAME,
            "channels_created": len(created),
            "total_channels": len(category.channels),
        }

    @property
    def guild_count(self) -> int:
        return len(self._registered_guilds)

    @staticmethod
    def get_channel_config(name: str) -> dict[str, Any] | None:
        """Get channel configuration by name."""
        for chan in CHANNEL_STRUCTURE:
            if chan["name"] == name:
                return chan
        return None
