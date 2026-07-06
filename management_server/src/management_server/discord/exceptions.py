"""
Discord registration exceptions — typed error hierarchy.
"""

from __future__ import annotations


class DiscordError(Exception):
    """Base exception for all Discord registration errors."""


class GuildNotFoundError(DiscordError):
    """Guild not found in database."""

    def __init__(self, guild_id: str) -> None:
        super().__init__(f"Guild not found: {guild_id}")


class GuildAlreadyRegisteredError(DiscordError):
    """Guild is already registered."""

    def __init__(self, guild_id: str) -> None:
        super().__init__(f"Guild already registered: {guild_id}")


class RegistrationError(DiscordError):
    """Guild registration failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ValidationError(DiscordError):
    """Registration validation failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class MachineAssociationError(DiscordError):
    """Machine association failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ConfigurationError(DiscordError):
    """Discord configuration error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class DiscordRepositoryError(DiscordError):
    """Database error during Discord operations."""
