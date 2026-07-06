"""
Discord Adapter exceptions — typed error hierarchy.
"""

from __future__ import annotations


class DiscordBotError(Exception):
    """Base exception for all Discord Bot errors."""


class GuildRegistrationError(DiscordBotError):
    """Guild registration failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ChannelCreationError(DiscordBotError):
    """Channel creation or synchronization failure."""

    def __init__(self, channel_name: str, detail: str = "") -> None:
        super().__init__(f"Channel '{channel_name}' error: {detail}")


class PermissionError(DiscordBotError):
    """Discord permission verification failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class StatusMessageError(DiscordBotError):
    """Status message management error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class RenderingError(DiscordBotError):
    """Notification rendering error."""

    def __init__(self, template: str, detail: str = "") -> None:
        super().__init__(f"Render '{template}' error: {detail}")


class ThreadError(DiscordBotError):
    """Incident thread management error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class APIClientError(DiscordBotError):
    """Management Server API client error."""

    def __init__(self, endpoint: str, status: int, detail: str = "") -> None:
        super().__init__(f"API {endpoint} returned {status}: {detail}")
