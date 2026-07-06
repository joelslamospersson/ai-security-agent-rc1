"""Discord Registration Framework for the Management Server."""

from management_server.discord.exceptions import (
    ConfigurationError,
    DiscordError,
    DiscordRepositoryError,
    GuildAlreadyRegisteredError,
    GuildNotFoundError,
    MachineAssociationError,
    RegistrationError,
    ValidationError,
)
from management_server.discord.manager import DiscordManager
from management_server.discord.metrics import DiscordMetricsCollector, DiscordMetricsSnapshot
from management_server.discord.models import (
    REQUIRED_CHANNELS,
    DiscordConfig,
    DiscordGuild,
    GuildSettings,
)
from management_server.discord.repository import DiscordRepository
from management_server.discord.schemas import (
    GuildConfigResponse,
    GuildDeleteResponse,
    GuildInfo,
    RegisterGuildRequest,
    RegisterGuildResponse,
    VerifyGuildRequest,
    VerifyGuildResponse,
)
from management_server.discord.service import DiscordService
from management_server.discord.validators import DiscordValidator

__all__ = [
    "REQUIRED_CHANNELS",
    "ConfigurationError",
    "DiscordConfig",
    "DiscordError",
    "DiscordGuild",
    "DiscordManager",
    "DiscordMetricsCollector",
    "DiscordMetricsSnapshot",
    "DiscordRepository",
    "DiscordRepositoryError",
    "DiscordService",
    "DiscordValidator",
    "GuildAlreadyRegisteredError",
    "GuildConfigResponse",
    "GuildDeleteResponse",
    "GuildInfo",
    "GuildNotFoundError",
    "GuildSettings",
    "MachineAssociationError",
    "RegisterGuildRequest",
    "RegisterGuildResponse",
    "RegistrationError",
    "ValidationError",
    "VerifyGuildRequest",
    "VerifyGuildResponse",
]
