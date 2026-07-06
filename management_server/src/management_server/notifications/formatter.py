"""
Notification formatter — formats notification payloads in various templates.

Supported formats:
    - JSON
    - Markdown
    - Plain Text
    - Discord Embed (structure only — no Discord integration)
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import structlog

from management_server.notifications.exceptions import FormatterError

logger = structlog.get_logger("notifications.formatter")


class NotificationFormatter(ABC):
    """Abstract base class for all notification formatters."""

    @abstractmethod
    def format(
        self,
        event_type: str,
        machine_id: str,
        destination: str,
        priority: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Format a notification payload."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Formatter name."""
        ...


class JsonFormatter(NotificationFormatter):
    """Formats notification as JSON."""

    name = "json"

    def format(
        self,
        event_type: str,
        machine_id: str,
        destination: str,
        priority: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        try:
            payload = {
                "event_type": event_type,
                "machine_id": machine_id,
                "destination": destination,
                "priority": priority,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {},
            }
            return json.dumps(payload, indent=2, default=str)
        except Exception as e:
            raise FormatterError("json", str(e)) from e


class MarkdownFormatter(NotificationFormatter):
    """Formats notification as Markdown."""

    name = "markdown"

    def format(
        self,
        event_type: str,
        machine_id: str,
        destination: str,
        priority: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        try:
            meta = metadata or {}
            lines = [
                f"# Notification: {event_type}",
                "",
                f"**Machine:** {machine_id}",
                f"**Destination:** {destination}",
                f"**Priority:** {priority}",
                f"**Timestamp:** {datetime.utcnow().isoformat()}",
                "",
            ]
            if meta:
                lines.append("## Metadata")
                for key, value in meta.items():
                    lines.append(f"- **{key}:** {value}")
            return "\n".join(lines)
        except Exception as e:
            raise FormatterError("markdown", str(e)) from e


class PlainTextFormatter(NotificationFormatter):
    """Formats notification as plain text."""

    name = "plain_text"

    def format(
        self,
        event_type: str,
        machine_id: str,
        destination: str,
        priority: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        try:
            meta = metadata or {}
            lines = [
                f"Notification: {event_type}",
                f"Machine: {machine_id}",
                f"Destination: {destination}",
                f"Priority: {priority}",
                f"Timestamp: {datetime.utcnow().isoformat()}",
            ]
            if meta:
                lines.append("")
                lines.append("Metadata:")
                for key, value in meta.items():
                    lines.append(f"  {key}: {value}")
            return "\n".join(lines)
        except Exception as e:
            raise FormatterError("plain_text", str(e)) from e


class DiscordEmbedFormatter(NotificationFormatter):
    """Formats notification as a Discord embed structure (no Discord integration).

    Produces a JSON object matching Discord's embed webhook format.
    """

    name = "discord_embed"

    def format(
        self,
        event_type: str,
        machine_id: str,
        destination: str,
        priority: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        try:
            meta = metadata or {}
            color_map = {
                "immediate": 0xFF0000,
                "high": 0xFF6600,
                "normal": 0x00AAFF,
                "low": 0x888888,
                "bulk": 0xAAAAAA,
            }
            embed = {
                "embeds": [
                    {
                        "title": f"Notification: {event_type}",
                        "color": color_map.get(priority, 0x00AAFF),
                        "fields": [
                            {"name": "Machine", "value": machine_id, "inline": True},
                            {"name": "Priority", "value": priority, "inline": True},
                            {"name": "Destination", "value": destination, "inline": True},
                        ],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ]
            }
            if meta:
                fields: list[dict[str, Any]] = embed["embeds"][0]["fields"]  # type: ignore[assignment]
                for key, value in meta.items():
                    fields.append({"name": key, "value": str(value), "inline": False})
            return json.dumps(embed, indent=2)
        except Exception as e:
            raise FormatterError("discord_embed", str(e)) from e


class FormatterRegistry:
    """Registry of available formatters."""

    def __init__(self) -> None:
        self._formatters: dict[str, NotificationFormatter] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for fmt in [
            JsonFormatter(),
            MarkdownFormatter(),
            PlainTextFormatter(),
            DiscordEmbedFormatter(),
        ]:
            self._formatters[fmt.name] = fmt

    def get(self, name: str) -> NotificationFormatter | None:
        """Get a formatter by name."""
        return self._formatters.get(name)

    def get_or_default(self, name: str) -> NotificationFormatter:
        """Get a formatter by name, falling back to JSON."""
        fmt = self._formatters.get(name)
        if fmt is None:
            logger.warning("Formatter not found, using JSON fallback", requested=name)
            return self._formatters.get("json", JsonFormatter())
        return fmt

    @property
    def available(self) -> list[str]:
        return list(self._formatters.keys())
