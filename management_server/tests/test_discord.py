"""
Tests for the Discord Registration Framework (Phase 16).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.discord.exceptions import (
    GuildAlreadyRegisteredError,
    GuildNotFoundError,
)
from management_server.discord.metrics import DiscordMetricsCollector
from management_server.discord.models import REQUIRED_CHANNELS
from management_server.discord.repository import DiscordRepository
from management_server.discord.schemas import RegisterGuildRequest, VerifyGuildRequest
from management_server.discord.service import DiscordService
from management_server.discord.validators import DiscordValidator

# ─── Validator Tests ──────────────────────────────────────────────────────


class TestDiscordValidator:
    def test_valid_registration(self):
        req = RegisterGuildRequest(guild_id="123456789012", name="Test Guild")
        errors = DiscordValidator.validate_registration(req)
        assert len(errors) == 0

    def test_missing_guild_id(self):
        req = RegisterGuildRequest(guild_id="", name="Test")
        errors = DiscordValidator.validate_registration(req)
        assert any("guild_id" in e for e in errors)

    def test_invalid_guild_id_short(self):
        req = RegisterGuildRequest(guild_id="123", name="Test")
        errors = DiscordValidator.validate_registration(req)
        assert any("too short" in e for e in errors)

    def test_validate_channel_ids_all_present(self):
        ids = {c["name"]: "123456789" for c in REQUIRED_CHANNELS}
        errors = DiscordValidator.validate_channel_ids(ids)
        assert len(errors) == 0

    def test_validate_channel_ids_missing(self):
        errors = DiscordValidator.validate_channel_ids({"is-bot-active": "123"})
        assert len(errors) >= 1

    def test_validate_channel_ids_invalid_id(self):
        ids = {c["name"]: "123" for c in REQUIRED_CHANNELS}
        errors = DiscordValidator.validate_channel_ids(ids)
        assert any("Invalid channel ID" in e for e in errors)


# ─── Metrics Tests ────────────────────────────────────────────────────────


class TestDiscordMetrics:
    def test_initial(self):
        m = DiscordMetricsCollector()
        snap = m.snapshot()
        assert snap.guilds_registered == 0

    def test_counters(self):
        m = DiscordMetricsCollector()
        m.guild_registered()
        m.guild_verified()
        m.guild_deleted()
        m.machine_associated()
        snap = m.snapshot()
        assert snap.guilds_registered == 1
        assert snap.guilds_verified == 1
        assert snap.guilds_deleted == 1
        assert snap.machines_associated == 1


# ─── Repository Tests ─────────────────────────────────────────────────────


class TestDiscordRepository:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = DiscordRepository(sqlite_session)
        self.session = sqlite_session

    async def test_create_and_get_guild(self):
        result = await self.repo.create_guild("123456789012", "Test Guild", "owner1")
        assert result["guild_id"] == "123456789012"

        got = await self.repo.get_guild("123456789012")
        assert got["name"] == "Test Guild"

    async def test_get_guild_not_found(self):
        with pytest.raises(GuildNotFoundError):
            await self.repo.get_guild("nonexistent")

    async def test_update_guild(self):
        await self.repo.create_guild("guild-1", "Original")
        updated = await self.repo.update_guild("guild-1", name="Updated")
        assert updated["name"] == "Updated"

    async def test_channel_mapping(self):
        await self.repo.create_guild("guild-2", "Test")
        await self.repo.set_channel_mapping("guild-2", "critical-alerts", "chan-123")
        mappings = await self.repo.get_channel_mappings("guild-2")
        assert len(mappings) >= 1
        assert mappings[0]["channel_id"] == "chan-123"

    async def test_associate_machine(self):
        await self.repo.create_guild("guild-3", "Test")
        result = await self.repo.associate_machine("guild-3", "machine-001")
        assert result["machine_uuid"] == "machine-001"
        machines = await self.repo.get_machines("guild-3")
        assert len(machines) >= 1

    async def test_delete_guild(self):
        await self.repo.create_guild("guild-4", "DeleteMe")
        await self.repo.delete_guild("guild-4")
        with pytest.raises(GuildNotFoundError):
            await self.repo.get_guild("guild-4")

    async def test_notification_preferences(self):
        await self.repo.create_guild("guild-5", "Test")
        await self.repo.set_notification_preference(
            "guild-5",
            "critical_alert",
            "critical-alerts",
            True,
        )
        prefs = await self.repo.get_notification_preferences("guild-5")
        assert len(prefs) >= 1
        assert prefs[0]["event_type"] == "critical_alert"

    async def test_list_guilds(self):
        await self.repo.create_guild("list-1", "A")
        await self.repo.create_guild("list-2", "B")
        _guilds, total = await self.repo.list_guilds()
        assert total >= 2


# ─── Service Tests ────────────────────────────────────────────────────────


class TestDiscordService:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = DiscordRepository(sqlite_session)
        self.service = DiscordService(repository=self.repo)

    async def test_register_guild(self):
        req = RegisterGuildRequest(guild_id="svc-guild-1a", name="Service Test")
        resp = await self.service.register_guild(req)
        assert resp.guild_id == "svc-guild-1a"
        assert resp.registered
        assert len(resp.required_channels) == 8

    async def test_register_duplicate_raises(self):
        req = RegisterGuildRequest(guild_id="svc-dup-long", name="Dup")
        await self.service.register_guild(req)
        with pytest.raises(GuildAlreadyRegisteredError):
            await self.service.register_guild(req)

    async def test_verify_guild(self):
        await self.service.register_guild(
            RegisterGuildRequest(guild_id="svc-verify-l", name="Verify")
        )
        channel_ids = {c["name"]: f"cid-{i}" for i, c in enumerate(REQUIRED_CHANNELS)}
        req = VerifyGuildRequest(
            guild_id="svc-verify-l",
            category_id="cat-123",
            channel_ids=channel_ids,
        )
        resp = await self.service.verify_guild(req)
        assert resp.verified

    async def test_verify_guild_missing_channels(self):
        await self.service.register_guild(
            RegisterGuildRequest(guild_id="svc-fail-lng", name="Fail")
        )
        req = VerifyGuildRequest(guild_id="svc-fail-lng", channel_ids={"only-one": "123"})
        resp = await self.service.verify_guild(req)
        assert not resp.verified

    async def test_get_guild(self):
        await self.service.register_guild(
            RegisterGuildRequest(guild_id="svc-get-long", name="GetMe")
        )
        info = await self.service.get_guild("svc-get-long")
        assert info["name"] == "GetMe"

    async def test_get_config(self):
        await self.service.register_guild(
            RegisterGuildRequest(guild_id="svc-config-lo", name="Config")
        )
        config = await self.service.get_config("svc-config-lo")
        assert config.guild_id == "svc-config-lo"
        assert len(config.required_channels) == 8

    async def test_delete_guild(self):
        await self.service.register_guild(RegisterGuildRequest(guild_id="svc-del-long", name="Del"))
        result = await self.service.delete_guild("svc-del-long")
        assert result["deleted"]

    async def test_get_metrics(self):
        metrics = await self.service.get_metrics()
        assert "guilds_total" in metrics

    async def test_list_guilds(self):
        await self.service.register_guild(RegisterGuildRequest(guild_id="svc-list1-lon", name="L1"))
        await self.service.register_guild(RegisterGuildRequest(guild_id="svc-list2-lon", name="L2"))
        guilds = await self.service.list_guilds()
        assert len(guilds) >= 2


# ─── API Tests ─────────────────────────────────────────────────────────────


class TestDiscordAPI:
    def test_register_no_db(self, client: TestClient):
        resp = client.post(
            "/api/v1/discord/register",
            json={"guild_id": "123456789012", "name": "Test"},
        )
        assert resp.status_code in (503,)

    def test_get_guild_no_db(self, client: TestClient):
        resp = client.get("/api/v1/discord/guild/test-id")
        assert resp.status_code in (503,)

    def test_get_config_no_db(self, client: TestClient):
        resp = client.get("/api/v1/discord/config/test-id")
        assert resp.status_code in (503,)
