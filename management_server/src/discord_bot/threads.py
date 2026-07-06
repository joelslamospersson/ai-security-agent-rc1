"""
Incident thread manager — creates and manages Discord threads for incidents.

Each incident gets a summary message + dedicated thread for updates.
"""

from __future__ import annotations

from typing import Any

import discord
import structlog

from discord_bot.exceptions import ThreadError
from discord_bot.renderer import NotificationRenderer

logger = structlog.get_logger("discord_bot.threads")

THREAD_CHANNEL = "critical-alerts"
MAX_ACTIVE_THREADS = 25


class IncidentThreadManager:
    """Manages incident threads in the critical-alerts channel."""

    def __init__(self, max_active: int = MAX_ACTIVE_THREADS) -> None:
        self._max_active = max_active
        self._active_threads: dict[str, Any] = {}
        self._total_created = 0

    async def create_incident_thread(
        self,
        guild: Any,
        incident_id: str,
        event_type: str,
        machine_id: str,
        description: str,
        auto_archive_minutes: int = 60,
    ) -> dict[str, Any]:
        """Create an incident thread with summary message."""
        channel = discord.utils.get(guild.text_channels, name=THREAD_CHANNEL)
        if channel is None:
            raise ThreadError(f"Channel '{THREAD_CHANNEL}' not found")

        # Enforce max active threads
        active_count = len(self._active_threads)
        if active_count >= self._max_active:
            logger.warning("Max active threads reached, archiving oldest")
            oldest = min(
                self._active_threads.keys(),
                key=lambda k: self._active_threads[k].get("created_at", ""),
            )
            await self.archive_thread(oldest)

        # Send summary message
        embed = NotificationRenderer.render_thread_summary(
            event_type=event_type,
            machine_id=machine_id,
            description=description,
        )
        msg = await channel.send(embed=embed["embeds"][0])

        # Create thread from message
        thread = await msg.create_thread(
            name=f"{event_type.replace('_', ' ').title()} — {machine_id[:16]}",
            auto_archive_duration=auto_archive_minutes,
        )

        self._active_threads[incident_id] = {
            "thread_id": thread.id,
            "channel_id": channel.id,
            "name": thread.name,
            "created_at": str(msg.created_at),
        }
        self._total_created += 1

        logger.info(
            "Incident thread created",
            incident=incident_id,
            thread=thread.name,
        )

        result: dict[str, Any] = self._active_threads[incident_id]
        return result

    async def append_update(
        self,
        incident_id: str,
        update_text: str,
        guild: Any,
    ) -> None:
        """Append an update to an existing incident thread."""
        thread_info = self._active_threads.get(incident_id)
        if thread_info is None:
            raise ThreadError(f"No active thread for incident: {incident_id}")

        try:
            thread = guild.get_thread(thread_info["thread_id"])
            if thread is None:
                # Archived or deleted
                del self._active_threads[incident_id]
                raise ThreadError(f"Thread for incident {incident_id} not found (archived?)")

            await thread.send(f"**Update:** {update_text}")
            logger.info("Incident thread updated", incident=incident_id)
        except ThreadError:
            raise
        except Exception as e:
            raise ThreadError(f"Failed to update thread: {e}") from e

    async def archive_thread(self, incident_id: str) -> None:
        """Archive an incident thread."""
        thread_info = self._active_threads.pop(incident_id, None)
        if thread_info is None:
            return
        logger.info("Incident thread archived", incident=incident_id)

    @property
    def total_created(self) -> int:
        return self._total_created

    @property
    def active_count(self) -> int:
        return len(self._active_threads)
