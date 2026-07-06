"""
Discord repository — database CRUD for guilds, settings, channel mappings, and preferences.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.discord.exceptions import GuildNotFoundError

logger = structlog.get_logger("discord.repository")


class DiscordRepository:
    """Persists Discord guild registrations and configuration."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_guild(self, guild_id: str, name: str, owner_id: str = "") -> dict[str, Any]:
        """Register a new guild."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                INSERT INTO discord_guilds (id, guild_id, name, owner_id, registered_at, active)
                VALUES (:id, :gid, :name, :owner, :now, TRUE)
            """),
            {
                "id": str(uuid.uuid4()),
                "gid": guild_id,
                "name": name,
                "owner": owner_id,
                "now": now,
            },
        )

        # Create default settings
        await self._session.execute(
            text("""
                INSERT INTO discord_guild_settings (id, guild_id, created_at, updated_at)
                VALUES (:id, :gid, :now, :now)
            """),
            {"id": str(uuid.uuid4()), "gid": guild_id, "now": now},
        )

        await self._session.commit()
        return await self.get_guild(guild_id)

    async def get_guild(self, guild_id: str) -> dict[str, Any]:
        """Get a guild by ID."""
        result = await self._session.execute(
            text("SELECT * FROM discord_guilds WHERE guild_id = :gid"),
            {"gid": guild_id},
        )
        row = result.fetchone()
        if row is None:
            raise GuildNotFoundError(guild_id)
        return dict(row._mapping)

    async def list_guilds(self) -> tuple[list[dict[str, Any]], int]:
        """List all registered guilds."""
        result = await self._session.execute(
            text("SELECT * FROM discord_guilds ORDER BY registered_at DESC")
        )
        rows = [dict(r._mapping) for r in result.fetchall()]
        return rows, len(rows)

    async def update_guild(self, guild_id: str, **kwargs: Any) -> dict[str, Any]:
        """Update guild fields."""
        col_map = {
            "category_id": "category_id",
            "verified": "verified",
            "active": "active",
            "name": "name",
            "owner_id": "owner_id",
        }
        sets: list[str] = []
        params: dict[str, object] = {"gid": guild_id}
        for key, value in kwargs.items():
            db_key = col_map.get(key, key)
            sets.append(f"{db_key} = :{key}")
            params[key] = value

        if sets:
            await self._session.execute(
                text(
                    f"UPDATE discord_guilds SET {', '.join(sets)}, updated_at = :now WHERE guild_id = :gid"
                ),
                {**params, "now": datetime.now(tz=UTC)},
            )
            await self._session.commit()

        return await self.get_guild(guild_id)

    async def delete_guild(self, guild_id: str) -> None:
        """Delete a guild and all associated data."""
        for table in [
            "discord_guilds",
            "discord_guild_settings",
            "discord_channel_mappings",
            "registered_machines",
            "notification_preferences",
            "ping_roles",
        ]:
            await self._session.execute(
                text(f"DELETE FROM {table} WHERE guild_id = :gid"),
                {"gid": guild_id},
            )
        await self._session.commit()

    async def get_settings(self, guild_id: str) -> dict[str, Any]:
        """Get guild settings."""
        result = await self._session.execute(
            text("SELECT * FROM discord_guild_settings WHERE guild_id = :gid"),
            {"gid": guild_id},
        )
        row = result.fetchone()
        if row is None:
            raise GuildNotFoundError(guild_id)
        return dict(row._mapping)

    async def update_settings(self, guild_id: str, **kwargs: Any) -> dict[str, Any]:
        """Update guild settings."""
        sets: list[str] = []
        params: dict[str, object] = {"gid": guild_id}
        for key, value in kwargs.items():
            db_key = key.replace("_", "")
            sets.append(f"{db_key} = :{key}")
            params[key] = value

        if sets:
            await self._session.execute(
                text(
                    f"UPDATE discord_guild_settings SET {', '.join(sets)}, updated_at = :now WHERE guild_id = :gid"
                ),
                {**params, "now": datetime.now(tz=UTC)},
            )
            await self._session.commit()

        return await self.get_settings(guild_id)

    async def set_channel_mapping(self, guild_id: str, channel_name: str, channel_id: str) -> None:
        """Set or update a channel mapping."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                INSERT INTO discord_channel_mappings (id, guild_id, channel_name, channel_id, created_at)
                VALUES (:id, :gid, :name, :cid, :now)
                ON CONFLICT (guild_id, channel_name) DO UPDATE SET
                    channel_id = EXCLUDED.channel_id
            """),
            {
                "id": str(uuid.uuid4()),
                "gid": guild_id,
                "name": channel_name,
                "cid": channel_id,
                "now": now,
            },
        )
        await self._session.commit()

    async def get_channel_mappings(self, guild_id: str) -> list[dict[str, Any]]:
        """Get all channel mappings for a guild."""
        result = await self._session.execute(
            text(
                "SELECT * FROM discord_channel_mappings WHERE guild_id = :gid ORDER BY channel_name"
            ),
            {"gid": guild_id},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def associate_machine(self, guild_id: str, machine_uuid: str) -> dict[str, Any]:
        """Associate a machine with a guild."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                INSERT INTO registered_machines (id, guild_id, machine_uuid, registered_at)
                VALUES (:id, :gid, :mu, :now)
                ON CONFLICT (machine_uuid) DO UPDATE SET
                    guild_id = EXCLUDED.guild_id
            """),
            {"id": str(uuid.uuid4()), "gid": guild_id, "mu": machine_uuid, "now": now},
        )
        await self._session.commit()
        return {"guild_id": guild_id, "machine_uuid": machine_uuid}

    async def get_machines(self, guild_id: str) -> list[dict[str, Any]]:
        """Get all machines associated with a guild."""
        result = await self._session.execute(
            text("SELECT * FROM registered_machines WHERE guild_id = :gid"),
            {"gid": guild_id},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def set_notification_preference(
        self,
        guild_id: str,
        event_type: str,
        channel_name: str,
        enabled: bool = True,
        ping_role_id: str = "",
    ) -> None:
        """Set a notification preference."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                INSERT INTO notification_preferences (id, guild_id, event_type, channel_name, enabled, ping_role_id, created_at)
                VALUES (:id, :gid, :et, :cn, :en, :pr, :now)
                ON CONFLICT (guild_id, event_type) DO UPDATE SET
                    channel_name = EXCLUDED.channel_name,
                    enabled = EXCLUDED.enabled,
                    ping_role_id = EXCLUDED.ping_role_id
            """),
            {
                "id": str(uuid.uuid4()),
                "gid": guild_id,
                "et": event_type,
                "cn": channel_name,
                "en": enabled,
                "pr": ping_role_id,
                "now": now,
            },
        )
        await self._session.commit()

    async def get_notification_preferences(self, guild_id: str) -> list[dict[str, Any]]:
        """Get notification preferences for a guild."""
        result = await self._session.execute(
            text("SELECT * FROM notification_preferences WHERE guild_id = :gid"),
            {"gid": guild_id},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def get_guild_count(self) -> int:
        result = await self._session.execute(text("SELECT COUNT(*) FROM discord_guilds"))
        return result.scalar() or 0

    async def get_machine_count(self, guild_id: str) -> int:
        result = await self._session.execute(
            text("SELECT COUNT(*) FROM registered_machines WHERE guild_id = :gid"),
            {"gid": guild_id},
        )
        return result.scalar() or 0
