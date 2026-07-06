"""
Tests for production hardening: health supervisor, worker supervisor, startup validation, emergency mode, shutdown.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from management_server.health.emergency import EmergencyMode
from management_server.health.models import HealthState
from management_server.health.supervisor import HealthSupervisor
from management_server.health.worker_supervisor import WorkerSupervisor


class TestHealthSupervisor:
    def test_register_and_update(self):
        hs = HealthSupervisor()
        hs.register("test_system")
        assert hs.get_health("test_system") is not None

        hs.update("test_system", HealthState.HEALTHY)
        health = hs.get_health("test_system")
        assert health is not None
        assert health.state == HealthState.HEALTHY

    def test_get_report(self):
        hs = HealthSupervisor()
        hs.register("a", HealthState.HEALTHY)
        hs.register("b", HealthState.HEALTHY)
        report = hs.get_report()
        assert report.healthy_count == 2
        assert report.overall == HealthState.HEALTHY

    def test_report_with_failures(self):
        hs = HealthSupervisor()
        hs.register("a", HealthState.HEALTHY)
        hs.register("b", HealthState.FAILED)
        report = hs.get_report()
        assert report.failed_count == 1
        assert report.overall == HealthState.FAILED

    def test_report_with_degraded(self):
        hs = HealthSupervisor()
        hs.register("a", HealthState.HEALTHY)
        hs.register("b", HealthState.DEGRADED)
        report = hs.get_report()
        assert report.degraded_count == 1
        assert report.overall == HealthState.DEGRADED

    def test_emergency_mode_propagation(self):
        hs = HealthSupervisor()
        assert not hs.emergency_mode
        hs.set_emergency_mode(True)
        assert hs.emergency_mode
        hs.set_emergency_mode(False)
        assert not hs.emergency_mode


class TestWorkerSupervisor:
    def test_register_and_heartbeat(self):
        ws = WorkerSupervisor()
        ws.register("worker-1")
        ws.heartbeat("worker-1")
        workers = ws.get_workers()
        assert "worker-1" in workers
        assert workers["worker-1"].status.value == "running"

    def test_mark_crashed(self):
        ws = WorkerSupervisor()
        ws.register("worker-1")
        ws.mark_crashed("worker-1", "OOM")
        workers = ws.get_workers()
        assert workers["worker-1"].status.value == "crashed"
        assert "OOM" in workers["worker-1"].error


class TestEmergencyMode:
    def test_initial_state(self):
        em = EmergencyMode()
        assert not em.active
        assert em.is_allowed("commands")

    def test_activate(self):
        em = EmergencyMode()
        em.activate("Database corruption")
        assert em.active
        assert not em.is_allowed("commands")
        assert not em.is_allowed("configsync")
        assert em.is_allowed("heartbeat")

    def test_deactivate(self):
        em = EmergencyMode()
        em.activate()
        em.deactivate()
        assert not em.active
        assert em.is_allowed("commands")

    def test_to_dict(self):
        em = EmergencyMode()
        em.activate("Test")
        d = em.to_dict()
        assert d["active"]
        assert d["reason"] == "Test"


class TestHealthEndpoint:
    def test_health_endpoint(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "application" in data
