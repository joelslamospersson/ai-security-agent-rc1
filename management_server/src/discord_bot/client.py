"""
Discord client — main bot client with event handlers and background tasks.

This is the entry point for the Discord Adapter process.
It communicates ONLY with the Management Server API.
Zero business logic — only rendering and state synchronization.
"""

from __future__ import annotations

import asyncio
from typing import Any

import discord
import structlog

from discord_bot.api_client import ManagementAPIClient
from discord_bot.config import DiscordBotSettings
from discord_bot.guild_manager import GuildManager
from discord_bot.metrics import DiscordBotMetricsCollector
from discord_bot.permissions import PermissionVerifier
from discord_bot.renderer import NotificationRenderer
from discord_bot.status import StatusMessageManager
from discord_bot.threads import IncidentThreadManager

logger = structlog.get_logger("discord_bot.client")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True


class DiscordBotClient(discord.Client):
    """Discord bot client for the AI Security Management Server."""

    def __init__(self, settings: DiscordBotSettings) -> None:
        super().__init__(intents=intents)
        self._settings = settings
        self._api_client = ManagementAPIClient(
            base_url=settings.api_base_url,
            api_key=settings.api_key,
            timeout_seconds=settings.api_timeout_seconds,
        )
        self._guild_manager = GuildManager()
        self._permission_verifier = PermissionVerifier()
        self._status_manager = StatusMessageManager()
        self._thread_manager = IncidentThreadManager(
            max_active=settings.max_active_threads,
        )
        self._renderer = NotificationRenderer()
        self._metrics = DiscordBotMetricsCollector()
        self._background_tasks: list[asyncio.Task[Any]] = []

    async def on_ready(self) -> None:
        """Bot is ready and connected to Discord."""
        logger.info(
            "Discord bot connected",
            user=str(self.user),
            guilds=len(self.guilds),
        )
        self._metrics.set_guild_count(len(self.guilds))

        if self._settings.register_on_start:
            for guild in self.guilds:
                if self._settings.allowed_guilds and guild.id not in self._settings.allowed_guilds:
                    continue
                await self._register_guild(guild)

        # Start background tasks
        self._background_tasks = [
            asyncio.create_task(self._status_update_loop()),
            asyncio.create_task(self._permission_check_loop()),
            asyncio.create_task(self._notification_poll_loop()),
        ]

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Handle new guild join — register and synchronize."""
        logger.info("Joined new guild", guild=guild.name, id=guild.id)
        await self._register_guild(guild)

    async def _register_guild(self, guild: discord.Guild) -> None:
        """Register guild and create channel structure."""
        try:
            await self._guild_manager.register_guild(str(guild.id), guild.name, self._api_client)
            sync_result = await self._guild_manager.synchronize(guild)
            self._metrics.channel_created()
            logger.info("Guild synchronized", **sync_result)
        except Exception as e:
            logger.error("Guild registration failed", guild=guild.name, error=str(e))

    async def _status_update_loop(self) -> None:
        """Background task: update status message every N seconds."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                for guild in self.guilds:
                    metrics = await self._api_client.get_metrics()
                    metrics["server_ok"] = True
                    await self._status_manager.update_status(guild, metrics)
                    self._metrics.status_updated()
            except Exception as e:
                logger.error("Status update failed", error=str(e))
            await asyncio.sleep(self._settings.status_update_interval_seconds)

    async def _permission_check_loop(self) -> None:
        """Background task: verify permissions every N seconds."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                for guild in self.guilds:
                    result = await self._permission_verifier.verify_guild(guild)
                    if result.get("repairs_succeeded", 0) > 0:
                        self._metrics.permission_repair()
                    if result.get("sensitive_compromised"):
                        logger.error(
                            "Sensitive channels compromised, stopping notifications",
                            guild=guild.name,
                        )
            except Exception as e:
                logger.error("Permission check failed", error=str(e))
            await asyncio.sleep(self._settings.permission_check_interval_seconds)

    async def _notification_poll_loop(self) -> None:
        """Background task: poll for pending notifications and render them."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                notifications = await self._api_client.get_pending_notifications()
                for notif in notifications:
                    await self._render_notification(notif)
            except Exception as e:
                logger.error("Notification poll failed", error=str(e))
            await asyncio.sleep(10)

    async def _render_notification(self, notif: dict[str, Any]) -> None:
        """Render a single notification to Discord."""
        event_type = notif.get("event_type", "unknown")
        severity = notif.get("severity", "info")
        machine_id = notif.get("machine_id", "")
        description = notif.get("payload", "")

        for guild in self.guilds:
            try:
                if severity == "critical":
                    embed = self._renderer.render_critical_alert(
                        event_type=event_type,
                        description=description,
                        machine_id=machine_id,
                    )
                    channel_name = "critical-alerts"
                else:
                    embed = self._renderer.render_embed(
                        event_type=event_type,
                        description=description,
                        machine_id=machine_id,
                        severity=severity,
                    )
                    channel_name = "system-events"

                channel = discord.utils.get(guild.text_channels, name=channel_name)
                if channel:
                    await channel.send(embed=embed["embeds"][0])
                    self._metrics.notification_rendered()
            except Exception as e:
                logger.error(
                    "Notification render failed",
                    event_type=event_type,
                    error=str(e),
                )

    async def close(self) -> None:
        """Clean shutdown."""
        for task in self._background_tasks:
            task.cancel()
        await super().close()
