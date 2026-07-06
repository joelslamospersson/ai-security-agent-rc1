"""
Permission verification — verifies Discord channel permissions every 60 seconds.

If repair is possible, repairs automatically.
If repair fails, stops sending sensitive notifications and notifies owners.
"""

from __future__ import annotations

from typing import Any

import discord
import structlog
from discord import PermissionOverwrite

from discord_bot.exceptions import PermissionError

logger = structlog.get_logger("discord_bot.permissions")

REQUIRED_PERMISSIONS: list[str] = [
    "read_messages",
    "send_messages",
    "embed_links",
    "attach_files",
    "read_message_history",
    "manage_threads",
    "create_public_threads",
    "send_messages_in_threads",
]

SENSITIVE_CHANNELS = ["critical-alerts", "audit-log", "pairing-log"]


class PermissionVerifier:
    """Verifies Discord channel permissions and repairs when possible."""

    def __init__(self) -> None:
        self._repair_count = 0
        self._last_check_result: dict[str, Any] = {}

    async def verify_guild(self, guild: Any) -> dict[str, Any]:
        """Verify permissions for all channels in the AI Security category."""
        result: dict[str, Any] = {
            "guild": guild.name,
            "category_found": False,
            "channels_checked": 0,
            "repairs_needed": 0,
            "repairs_succeeded": 0,
            "repairs_failed": 0,
            "sensitive_compromised": False,
        }

        category = discord.utils.get(guild.categories, name="AI Security")
        if category is None:
            result["category_found"] = False
            return result

        result["category_found"] = True

        bot_member = guild.me
        if bot_member is None:
            raise PermissionError("Bot member not found in guild")

        for channel in category.channels:
            result["channels_checked"] += 1
            perms = channel.permissions_for(bot_member)

            missing = [p for p in REQUIRED_PERMISSIONS if not getattr(perms, p, False)]
            if not missing:
                continue

            result["repairs_needed"] += 1
            try:
                overwrites = {
                    guild.default_role: PermissionOverwrite(read_messages=False),
                    bot_member: PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        embed_links=True,
                        attach_files=True,
                        read_message_history=True,
                        manage_threads=True,
                        create_public_threads=True,
                        send_messages_in_threads=True,
                    ),
                }
                await channel.edit(overwrites=overwrites)
                result["repairs_succeeded"] += 1
                self._repair_count += 1
                logger.info("Channel permissions repaired", channel=channel.name, missing=missing)
            except Exception as e:
                result["repairs_failed"] += 1
                logger.error("Channel permission repair failed", channel=channel.name, error=str(e))
                if channel.name in SENSITIVE_CHANNELS:
                    result["sensitive_compromised"] = True

        self._last_check_result = result
        return result

    @property
    def repair_count(self) -> int:
        return self._repair_count

    @property
    def last_check(self) -> dict[str, Any]:
        return dict(self._last_check_result)
