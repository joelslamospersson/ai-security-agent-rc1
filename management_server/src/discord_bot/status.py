"""
Status message manager — maintains exactly one editable status message.

Updates every 30 seconds with current system state.
Never creates duplicate status messages.
"""

from __future__ import annotations

from typing import Any

import discord
import structlog

from discord_bot.exceptions import StatusMessageError
from discord_bot.renderer import NotificationRenderer

logger = structlog.get_logger("discord_bot.status")

STATUS_CHANNEL = "bot-status"


class StatusMessageManager:
    """Manages the single status message in the bot-status channel."""

    def __init__(self) -> None:
        self._message: Any = None
        self._channel: Any = None
        self._update_count = 0

    async def ensure_status_channel(self, guild: Any) -> Any:
        """Find or create the status channel."""
        category = discord.utils.get(guild.categories, name="AI Security")
        if category is None:
            raise StatusMessageError("AI Security category not found")

        channel = discord.utils.get(category.text_channels, name=STATUS_CHANNEL)
        if channel is None:
            channel = await guild.create_text_channel(STATUS_CHANNEL, category=category)
            logger.info("Status channel created", guild=guild.name)

        self._channel = channel
        return channel

    async def update_status(self, guild: Any, metrics: dict[str, Any]) -> dict[str, Any]:
        """Update or create the single status message."""
        channel = self._channel
        if channel is None:
            channel = await self.ensure_status_channel(guild)

        # Build status fields from metrics
        fields = NotificationRenderer.build_status_fields(
            agent_status=metrics.get("agent_status", "unknown"),
            server_status="healthy" if metrics.get("server_ok") else "degraded",
            cpu_percent=float(metrics.get("cpu_percent", 0)),
            ram_percent=float(metrics.get("ram_percent", 0)),
            uptime_hours=float(metrics.get("uptime_hours", 0)),
            last_heartbeat=str(metrics.get("last_heartbeat", "never")),
            tracked_machines=int(metrics.get("tracked_machines", 0)),
            online_machines=int(metrics.get("online_machines", 0)),
            offline_machines=int(metrics.get("offline_machines", 0)),
            queue_depth=int(metrics.get("queue_depth", 0)),
            trust_score=str(metrics.get("trust_score", "N/A")),
            posture=str(metrics.get("posture", "unknown")),
        )

        embed = NotificationRenderer.render_status_embed(
            title="AI Security — System Status",
            fields=fields,
            color=0x00FF00 if metrics.get("server_ok") else 0xFF0000,
        )

        content = metrics.get("status_message", "AI Security Management System — Operational")

        try:
            if self._message is None:
                # Find existing status message or create new
                async for msg in channel.history(limit=50):
                    if msg.author == guild.me and msg.embeds:
                        self._message = msg
                        break

            if self._message is not None:
                await self._message.edit(content=content, embed=embed["embeds"][0])
            else:
                msg = await channel.send(content=content, embed=embed["embeds"][0])
                self._message = msg

            self._update_count += 1
            return {"updated": True, "count": self._update_count}
        except Exception as e:
            raise StatusMessageError(f"Status update failed: {e}") from e

    @property
    def update_count(self) -> int:
        return self._update_count
