"""
Discord registration validators — validates guild registration requests.
"""

from __future__ import annotations

import structlog

from management_server.discord.exceptions import ValidationError
from management_server.discord.schemas import RegisterGuildRequest

logger = structlog.get_logger("discord.validators")


class DiscordValidator:
    """Validates Discord registration requests and configuration."""

    @staticmethod
    def validate_registration(request: RegisterGuildRequest) -> list[str]:
        """Validate a guild registration request. Returns list of errors."""
        errors: list[str] = []

        if not request.guild_id:
            errors.append("guild_id is required")
        elif len(request.guild_id) < 10:
            errors.append("guild_id appears invalid (too short)")

        if not request.name:
            errors.append("name is required")

        if request.pairing_token and len(request.pairing_token) < 8:
            errors.append("pairing_token appears invalid (too short)")

        return errors

    @staticmethod
    def validate_and_raise(request: RegisterGuildRequest) -> None:
        """Validate and raise on first error."""
        errors = DiscordValidator.validate_registration(request)
        if errors:
            raise ValidationError(errors[0])

    @staticmethod
    def validate_guild_id(guild_id: str) -> None:
        """Validate a guild ID."""
        if not guild_id:
            raise ValidationError("guild_id is required")
        if len(guild_id) < 10:
            raise ValidationError(f"Invalid guild_id: {guild_id}")

    @staticmethod
    def validate_channel_ids(channel_ids: dict[str, str]) -> list[str]:
        """Validate channel ID mappings."""
        errors: list[str] = []
        required_names = {
            "is-bot-active",
            "critical-alerts",
            "detections",
            "ai-actions",
            "monitored-addresses",
            "security-reports",
            "audit",
            "bot-log",
        }
        provided = set(channel_ids.keys())
        missing = required_names - provided
        if missing:
            errors.append(f"Missing channel IDs for: {', '.join(sorted(missing))}")
        for name, cid in channel_ids.items():
            if not cid or len(str(cid)) < 5:
                errors.append(f"Invalid channel ID for '{name}'")
        return errors
