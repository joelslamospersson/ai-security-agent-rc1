"""
Discord Adapter configuration via pydantic-settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DiscordBotSettings(BaseSettings):
    """Configuration for the Discord Adapter process."""

    model_config = SettingsConfigDict(
        env_prefix="DISCORD_",
        env_file=".env",
        extra="ignore",
    )

    # Discord
    token: str = Field(default="", description="Discord bot token")
    application_id: int | None = Field(default=None, description="Discord application ID")

    # Management Server API
    api_base_url: str = Field(
        default="http://localhost:8000", description="Management Server API URL (overridable via DISCORD_API_BASE_URL env var)"
    )
    api_key: str = Field(default="", description="API key for Management Server")
    api_timeout_seconds: int = Field(default=30, ge=1)

    # Guild
    register_on_start: bool = Field(default=True, description="Auto-register guild on startup")
    allowed_guilds: list[str] = Field(
        default_factory=list, description="Restrict to these guild IDs"
    )

    # Permissions
    permission_check_interval_seconds: int = Field(default=60, ge=10)
    status_update_interval_seconds: int = Field(default=30, ge=5)

    # Status
    status_channel_name: str = Field(default="bot-status")
    status_message_content: str = Field(default="AI Security — Starting up...")

    # Rendering
    default_color: int = Field(default=0x00AAFF, description="Default embed color")
    critical_color: int = Field(default=0xFF0000, description="Critical alert color")
    warning_color: int = Field(default=0xFF6600, description="Warning alert color")
    success_color: int = Field(default=0x00FF00, description="Success alert color")

    # Threads
    max_active_threads: int = Field(default=25, ge=1, le=100)
    auto_archive_minutes: int = Field(default=60, ge=5, le=10080)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="console")


def load_discord_config(path: str | None = None) -> dict[str, Any]:
    """Load optional YAML config file for additional settings."""
    config_path = Path(path or "config/discord.yaml")
    if config_path.exists():
        with open(config_path) as f:
            return dict(yaml.safe_load(f) or {})
    return {}
