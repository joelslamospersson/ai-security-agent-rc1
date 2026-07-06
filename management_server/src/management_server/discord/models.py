"""
Discord registration models — guilds, settings, channel mappings, and preferences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

REQUIRED_CHANNELS: list[dict[str, str]] = [
    {"name": "is-bot-active", "description": "Bot status and health"},
    {"name": "critical-alerts", "description": "Critical security alerts"},
    {"name": "detections", "description": "Security detections log"},
    {"name": "ai-actions", "description": "AI-driven actions"},
    {"name": "monitored-addresses", "description": "Monitored IPs and addresses"},
    {"name": "security-reports", "description": "Periodic security reports"},
    {"name": "audit", "description": "Immutable audit log"},
    {"name": "bot-log", "description": "Bot operation logs"},
]

DEFAULT_CATEGORY_NAME = "AI Security"

DEFAULT_PERMISSION_RULES: dict[str, Any] = {
    "private_channels": True,
    "view_only": True,
    "no_external_sharing": True,
}


@dataclass
class DiscordGuild:
    """A registered Discord guild."""

    guild_id: str = ""
    name: str = ""
    owner_id: str = ""
    category_id: str = ""
    channel_ids: dict[str, str] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    verified: bool = False
    active: bool = True


@dataclass
class GuildSettings:
    """Configuration settings for a Discord guild."""

    guild_id: str = ""
    category_name: str = DEFAULT_CATEGORY_NAME
    required_channels: list[dict[str, str]] = field(default_factory=lambda: list(REQUIRED_CHANNELS))
    permission_rules: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_PERMISSION_RULES))
    heartbeat_interval_seconds: int = 30
    notification_channel: str = "critical-alerts"
    ping_role_id: str = ""
    maintenance_mode: bool = False
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass
class ChannelMapping:
    """Mapping of channel names to Discord channel IDs for a guild."""

    guild_id: str = ""
    channel_name: str = ""
    channel_id: str = ""
    channel_type: str = "text"
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass
class NotificationPreference:
    """Per-guild notification preferences."""

    guild_id: str = ""
    event_type: str = ""
    channel_name: str = "system-events"
    enabled: bool = True
    ping_role_id: str = ""


@dataclass
class PingRole:
    """Role to ping for specific event types."""

    guild_id: str = ""
    role_id: str = ""
    event_type: str = "critical"
    mention: bool = True


@dataclass
class DiscordConfig:
    """Complete configuration returned to the Discord Bot for a guild."""

    guild_id: str = ""
    category_name: str = DEFAULT_CATEGORY_NAME
    required_channels: list[dict[str, str]] = field(default_factory=lambda: list(REQUIRED_CHANNELS))
    permission_rules: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_PERMISSION_RULES))
    heartbeat_interval_seconds: int = 30
    notification_channel: str = "critical-alerts"
    notification_preferences: list[dict[str, Any]] = field(default_factory=list)
    ping_roles: list[dict[str, Any]] = field(default_factory=list)
    maintenance_mode: bool = False
