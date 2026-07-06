"""
Notification renderer — renders immutable Notification objects into Discord
embeds and markdown messages.

Zero business logic. Only rendering.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog

from discord_bot.exceptions import RenderingError

logger = structlog.get_logger("discord_bot.renderer")

COLOR_MAP: dict[str, int] = {
    "immediate": 0xFF0000,
    "critical": 0xFF0000,
    "high": 0xFF6600,
    "warning": 0xFF6600,
    "normal": 0x00AAFF,
    "info": 0x00AAFF,
    "low": 0x888888,
    "bulk": 0xAAAAAA,
    "success": 0x00FF00,
}

SEVERITY_COLORS: dict[str, int] = {
    "critical": 0xFF0000,
    "error": 0xCC0000,
    "warning": 0xFF6600,
    "info": 0x00AAFF,
    "debug": 0x888888,
}

MAX_EMBED_LENGTH = 6000
MAX_FIELD_VALUE_LENGTH = 1024


class NotificationRenderer:
    """Renders notifications into Discord-compatible formats."""

    @staticmethod
    def render_embed(
        event_type: str,
        description: str,
        machine_id: str = "",
        priority: str = "normal",
        severity: str = "info",
        destination: str = "discord",
        metadata: dict[str, Any] | None = None,
        color: int | None = None,
    ) -> dict[str, Any]:
        """Render a notification as a Discord embed."""
        try:
            if color is None:
                color = COLOR_MAP.get(priority, COLOR_MAP.get(severity, 0x00AAFF))

            embed = {
                "embeds": [
                    {
                        "title": f"AI Security — {event_type.replace('_', ' ').title()}",
                        "color": color,
                        "timestamp": datetime.utcnow().isoformat(),
                        "fields": [],
                        "footer": {"text": "AI Security Management Server"},
                    }
                ]
            }

            if description:
                embed["embeds"][0]["description"] = description[:MAX_EMBED_LENGTH]

            fields: list[dict[str, Any]] = embed["embeds"][0]["fields"]  # type: ignore[assignment]

            if machine_id:
                fields.append({"name": "Machine", "value": machine_id[:256], "inline": True})
            fields.append({"name": "Priority", "value": priority.title(), "inline": True})
            fields.append({"name": "Severity", "value": severity.title(), "inline": True})
            fields.append({"name": "Destination", "value": destination, "inline": True})

            if metadata:
                for key, value in metadata.items():
                    if key in ("token", "password", "secret", "key", "private_key"):
                        continue
                    str_val = str(value)[:MAX_FIELD_VALUE_LENGTH]
                    fields.append(
                        {"name": key.replace("_", " ").title(), "value": str_val, "inline": False}
                    )

            return embed
        except Exception as e:
            raise RenderingError("discord_embed", str(e)) from e

    @staticmethod
    def render_critical_alert(
        event_type: str,
        description: str,
        machine_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Render a critical alert with ping-worthy embed."""
        return NotificationRenderer.render_embed(
            event_type=f"🚨 {event_type}",
            description=description,
            machine_id=machine_id,
            priority="immediate",
            severity="critical",
            color=0xFF0000,
            metadata=metadata,
        )

    @staticmethod
    def render_status_embed(
        title: str,
        fields: list[dict[str, Any]],
        color: int = 0x00AAFF,
    ) -> dict[str, Any]:
        """Render a status update embed."""
        return {
            "embeds": [
                {
                    "title": title,
                    "color": color,
                    "timestamp": datetime.utcnow().isoformat(),
                    "fields": fields[:25],
                    "footer": {"text": f"Updated {datetime.utcnow().strftime('%H:%M:%S UTC')}"},
                }
            ]
        }

    @staticmethod
    def render_thread_summary(
        event_type: str,
        machine_id: str,
        description: str,
        updates: list[str] | None = None,
    ) -> dict[str, Any]:
        """Render an incident thread summary message."""
        embed = NotificationRenderer.render_embed(
            event_type=event_type,
            description=description,
            machine_id=machine_id,
            priority="high",
            severity="warning",
        )
        if updates:
            update_text = "\n".join(f"• {u}" for u in updates[-10:])
            embed["embeds"][0]["fields"].append(
                {
                    "name": "Updates",
                    "value": update_text[:MAX_FIELD_VALUE_LENGTH],
                    "inline": False,
                }
            )
        return embed

    @staticmethod
    def render_markdown(
        event_type: str,
        description: str,
        machine_id: str = "",
        priority: str = "normal",
        severity: str = "info",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Render a notification as Discord markdown."""
        try:
            lines = [
                f"**AI Security — {event_type.replace('_', ' ').title()}**",
                "",
            ]
            if description:
                lines.append(f"{description}")
                lines.append("")

            if machine_id:
                lines.append(f"**Machine:** {machine_id}")
            lines.append(f"**Priority:** {priority.title()}")
            lines.append(f"**Severity:** {severity.title()}")

            if metadata:
                lines.append("")
                lines.append("**Details:**")
                for key, value in metadata.items():
                    if key in ("token", "password", "secret", "key", "private_key"):
                        continue
                    lines.append(f"• **{key.replace('_', ' ').title()}:** {value}")

            return "\n".join(lines)
        except Exception as e:
            raise RenderingError("markdown", str(e)) from e

    @staticmethod
    def build_status_fields(
        agent_status: str = "unknown",
        server_status: str = "unknown",
        adapter_status: str = "running",
        cpu_percent: float = 0.0,
        ram_percent: float = 0.0,
        uptime_hours: float = 0.0,
        last_heartbeat: str = "never",
        tracked_machines: int = 0,
        online_machines: int = 0,
        offline_machines: int = 0,
        queue_depth: int = 0,
        trust_score: str = "N/A",
        posture: str = "unknown",
    ) -> list[dict[str, Any]]:
        """Build status embed fields from metrics data."""
        return [
            {"name": "Agent Status", "value": agent_status.title(), "inline": True},
            {"name": "Server Status", "value": server_status.title(), "inline": True},
            {"name": "Adapter Status", "value": adapter_status.title(), "inline": True},
            {"name": "CPU", "value": f"{cpu_percent:.1f}%", "inline": True},
            {"name": "RAM", "value": f"{ram_percent:.1f}%", "inline": True},
            {"name": "Uptime", "value": f"{uptime_hours:.1f}h", "inline": True},
            {"name": "Last Heartbeat", "value": last_heartbeat, "inline": True},
            {"name": "Tracked Machines", "value": str(tracked_machines), "inline": True},
            {"name": "Online", "value": str(online_machines), "inline": True},
            {"name": "Offline", "value": str(offline_machines), "inline": True},
            {"name": "Queue Depth", "value": str(queue_depth), "inline": True},
            {"name": "Trust Score", "value": trust_score, "inline": True},
            {"name": "Security Posture", "value": posture.title(), "inline": True},
        ]
