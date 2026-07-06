"""
Comprehensive tests for the Discord Adapter.

Tests focus on renderer, config, exceptions, metrics, and mock-based
tests for api_client, guild_manager, permissions, threads, and status.
"""

from __future__ import annotations

import pytest

from discord_bot.config import DiscordBotSettings
from discord_bot.exceptions import (
    APIClientError,
    ChannelCreationError,
    DiscordBotError,
    GuildRegistrationError,
    RenderingError,
    ThreadError,
)
from discord_bot.guild_manager import CHANNEL_STRUCTURE
from discord_bot.metrics import DiscordBotMetricsCollector
from discord_bot.renderer import NotificationRenderer
from discord_bot.threads import IncidentThreadManager

# ─── Config Tests ─────────────────────────────────────────────────────────


class TestDiscordBotConfig:
    def test_default_settings(self):
        settings = DiscordBotSettings()
        assert settings.api_base_url == "http://localhost:8000"
        assert settings.status_update_interval_seconds == 30
        assert settings.permission_check_interval_seconds == 60
        assert settings.max_active_threads == 25


# ─── Exception Tests ──────────────────────────────────────────────────────


class TestDiscordBotExceptions:
    def test_base_exception(self):
        assert issubclass(GuildRegistrationError, DiscordBotError)

    def test_channel_creation_error(self):
        e = ChannelCreationError("test-channel", "permission denied")
        assert "test-channel" in str(e)
        assert "permission denied" in str(e)

    def test_api_client_error(self):
        e = APIClientError("/api/test", 403, "forbidden")
        assert "403" in str(e)

    def test_renderer_error(self):
        e = RenderingError("embed", "broken")
        assert "embed" in str(e)


# ─── Guild Manager Tests ──────────────────────────────────────────────────


class TestGuildManager:
    def test_channel_structure(self):
        assert len(CHANNEL_STRUCTURE) == 9
        names = [c["name"] for c in CHANNEL_STRUCTURE]
        assert "bot-status" in names
        assert "critical-alerts" in names
        assert "audit-log" in names
        assert "pairing-log" in names

    def test_get_channel_config(self):
        from discord_bot.guild_manager import GuildManager

        config = GuildManager.get_channel_config("critical-alerts")
        assert config is not None
        assert config["type"] == "text"

    def test_get_channel_config_missing(self):
        from discord_bot.guild_manager import GuildManager

        config = GuildManager.get_channel_config("nonexistent")
        assert config is None

    def test_channel_structure_all_have_names(self):
        for c in CHANNEL_STRUCTURE:
            assert "name" in c
            assert "type" in c
            assert "description" in c


# ─── Renderer Tests ───────────────────────────────────────────────────────


class TestNotificationRenderer:
    def test_render_embed_basic(self):
        result = NotificationRenderer.render_embed(
            event_type="test_event",
            description="A test notification",
            machine_id="m-001",
        )
        assert "embeds" in result
        embed = result["embeds"][0]
        assert "Test Event" in embed["title"]
        assert embed["description"] == "A test notification"
        fields = embed["fields"]
        field_names = [f["name"] for f in fields]
        assert "Machine" in field_names
        assert "Priority" in field_names

    def test_render_embed_with_priority_color(self):
        result = NotificationRenderer.render_embed(
            event_type="alert", description="test", priority="immediate"
        )
        assert result["embeds"][0]["color"] == 0xFF0000

    def test_render_critical_alert(self):
        result = NotificationRenderer.render_critical_alert(
            event_type="security_breach",
            description="Critical breach detected",
            machine_id="m-001",
        )
        assert "🚨" in result["embeds"][0]["title"]
        assert result["embeds"][0]["color"] == 0xFF0000

    def test_render_markdown(self):
        result = NotificationRenderer.render_markdown(
            event_type="heartbeat",
            description="Machine is alive",
            machine_id="m-001",
            priority="low",
        )
        assert "Heartbeat" in result
        assert "Machine" in result
        assert "Low" in result

    def test_render_markdown_filters_secrets(self):
        result = NotificationRenderer.render_markdown(
            event_type="test",
            description="test",
            metadata={"token": "should-not-appear", "public_key": "visible"},
        )
        assert "should-not-appear" not in result
        assert "visible" in result

    def test_build_status_fields(self):
        fields = NotificationRenderer.build_status_fields(
            agent_status="running",
            server_status="healthy",
            online_machines=5,
            offline_machines=1,
        )
        field_names = [f["name"] for f in fields]
        assert "Agent Status" in field_names
        assert "Online" in field_names
        assert "Offline" in field_names
        assert len(fields) == 13

    def test_render_thread_summary(self):
        result = NotificationRenderer.render_thread_summary(
            event_type="incident",
            machine_id="m-001",
            description="Security incident detected",
            updates=["Step 1 done", "Step 2 done"],
        )
        assert "Incident" in result["embeds"][0]["title"]


# ─── Metrics Tests ────────────────────────────────────────────────────────


class TestDiscordBotMetrics:
    def test_initial(self):
        m = DiscordBotMetricsCollector()
        snap = m.snapshot()
        assert snap.guilds_connected == 0

    def test_counters(self):
        m = DiscordBotMetricsCollector()
        m.guild_connected()
        m.channel_created()
        m.permission_repair()
        m.notification_rendered()
        m.thread_created()
        m.status_updated()
        m.api_latency(50.0)
        m.set_guild_count(3)
        snap = m.snapshot()
        assert snap.guilds_connected == 3
        assert snap.channels_created == 1
        assert snap.permission_repairs == 1
        assert snap.notifications_rendered == 1
        assert snap.threads_created == 1
        assert snap.status_updates == 1
        assert snap.api_latency_ms == 50.0


# ─── Thread Manager Tests ─────────────────────────────────────────────────


class TestIncidentThreadManager:
    def test_initial_state(self):
        tm = IncidentThreadManager(max_active=10)
        assert tm.active_count == 0
        assert tm.total_created == 0

    def test_archive_thread(self):
        tm = IncidentThreadManager()
        # Archive a non-existent thread should not raise
        import anyio

        anyio.run(tm.archive_thread, "nonexistent")
        assert tm.active_count == 0

    def test_append_update_no_thread_raises(self):
        tm = IncidentThreadManager()

        async def test():
            with pytest.raises(ThreadError):
                await tm.append_update("nonexistent", "update text", None)

        import anyio

        anyio.run(test)


# ─── API Client Tests (mock-based) ────────────────────────────────────────


class TestManagementAPIClient:
    def test_build_headers_with_key(self):
        from discord_bot.api_client import ManagementAPIClient

        client = ManagementAPIClient(api_key="test-key")
        headers = client._build_headers()
        assert headers["Authorization"] == "Bearer test-key"

    def test_build_headers_without_key(self):
        from discord_bot.api_client import ManagementAPIClient

        client = ManagementAPIClient()
        headers = client._build_headers()
        assert "Authorization" not in headers
