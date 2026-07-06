"""
Discord Adapter — main entry point.

This is a SEPARATE PROCESS from the Management Server.
It communicates ONLY with the Management Server REST API.
It never queries the database directly.
It contains zero business logic.

Usage:
    python -m discord_bot.main
"""

from __future__ import annotations

import sys

import structlog

from discord_bot.client import DiscordBotClient
from discord_bot.config import DiscordBotSettings

logger = structlog.get_logger("discord_bot.main")


def main() -> None:
    """Start the Discord Adapter process."""
    settings = DiscordBotSettings()

    if not settings.token:
        logger.error("DISCORD_TOKEN not set — cannot start Discord bot")
        sys.exit(1)

    client = DiscordBotClient(settings)

    try:
        logger.info("Starting Discord Adapter...")
        client.run(settings.token, log_handler=None)
    except KeyboardInterrupt:
        logger.info("Discord Adapter shutting down")
    except Exception as e:
        logger.error("Discord Adapter failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
