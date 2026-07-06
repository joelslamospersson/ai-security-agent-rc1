"""
Tests for the Integration Test Harness components.
"""

from __future__ import annotations

from integration_harness.fake_agent import FakeAgent
from integration_harness.fake_attacker import FakeAttacker
from integration_harness.fake_discord import FakeDiscordAdapter
from integration_harness.fake_journald import FakeJournald
from integration_harness.fake_management import FakeManagementServer
from integration_harness.fake_network import FakeNetwork
from integration_harness.time_controller import TimeController


class TestFakeAgent:
    def test_create_heartbeat(self):
        agent = FakeAgent()
        hb = agent.create_heartbeat()
        assert hb["machine_uuid"] == agent.machine_uuid
        assert hb["protocol_version"] == "1.0"
        assert hb["sequence_number"] > 0

    def test_sequence_increments(self):
        agent = FakeAgent()
        hb1 = agent.create_heartbeat()
        hb2 = agent.create_heartbeat()
        assert hb2["sequence_number"] > hb1["sequence_number"]

    def test_generate_ssh_events(self):
        agent = FakeAgent()
        events = agent.generate_ssh_brute_force_events(5)
        assert len(events) == 5
        assert events[0]["event_type"] == "ssh_failed_login"


class TestFakeAttacker:
    def test_ssh_brute_force(self):
        attacker = FakeAttacker()
        events = attacker.ssh_brute_force(attempts=10)
        assert len(events) == 10
        assert all(e["attack_type"] == "ssh_brute_force" for e in events)

    def test_deterministic_replay(self):
        a1 = FakeAttacker(seed=42)
        a2 = FakeAttacker(seed=42)
        e1 = a1.ssh_brute_force(attempts=5)
        e2 = a2.ssh_brute_force(attempts=5)
        assert len(e1) == len(e2)

    def test_multiple_attack_types(self):
        attacker = FakeAttacker()
        events = attacker.password_spraying()
        assert all(e["attack_type"] == "password_spraying" for e in events)


class TestFakeManagement:
    async def test_process_heartbeat(self):
        mgmt = FakeManagementServer()
        agent = FakeAgent()
        hb = agent.create_heartbeat()
        resp = await mgmt.process_heartbeat(hb)
        assert resp["acknowledged"]
        assert mgmt.heartbeat_count == 1

    async def test_pending_commands(self):
        mgmt = FakeManagementServer()
        cmd_id = mgmt.add_pending_command("restart_agent")
        assert len(mgmt.commands_pending) == 1

        agent = FakeAgent()
        hb = agent.create_heartbeat()
        resp = await mgmt.process_heartbeat(hb)
        assert len(resp.get("pending_commands", [])) == 1

    async def test_audit_events(self):
        mgmt = FakeManagementServer()
        agent = FakeAgent()
        await mgmt.process_heartbeat(agent.create_heartbeat())
        assert mgmt.audit_count == 1


class TestFakeDiscord:
    async def test_render_notification(self):
        discord = FakeDiscordAdapter()
        result = await discord.render_notification({
            "notification_id": "n1",
            "event_type": "test",
            "severity": "critical",
        })
        assert result["sent"]
        assert result["channel"] == "critical-alerts"
        assert discord.notification_count == 1

    async def test_unhealthy(self):
        discord = FakeDiscordAdapter()
        discord.set_unhealthy()
        result = await discord.render_notification({"event_type": "test"})
        assert not result["sent"]


class TestFakeNetwork:
    def test_initial_healthy(self):
        net = FakeNetwork()
        assert net.is_healthy

    def test_partition(self):
        net = FakeNetwork()
        net.partition()
        assert not net.is_healthy

    def test_heal(self):
        net = FakeNetwork()
        net.partition()
        net.heal()
        assert net.is_healthy


class TestTimeController:
    def test_initial_time(self):
        tc = TimeController()
        assert tc.now() > 0

    def test_advance(self):
        tc = TimeController()
        before = tc.now()
        tc.advance(60)
        assert tc.now() >= before + 60

    def test_pause_resume(self):
        tc = TimeController()
        tc.pause()
        paused = tc.now()
        tc.advance(60)
        assert tc.now() == paused
        tc.resume()
        assert tc.now() >= paused


class TestFakeJournald:
    def test_generate_ssh_logs(self):
        jd = FakeJournald()
        logs = jd.generate_ssh_brute_force(10)
        assert len(logs) == 10
        assert all(log["source"] == "sshd" for log in logs)

    def test_clear(self):
        jd = FakeJournald()
        jd.generate_ssh_brute_force(5)
        assert len(jd.get_recent()) == 5
        jd.clear()
        assert len(jd.get_recent()) == 0
