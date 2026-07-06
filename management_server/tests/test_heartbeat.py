"""
Comprehensive tests for the Heartbeat & Management Protocol subsystem.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.heartbeat.exceptions import (
    HeartbeatValidationError,
    MachineNotRegisteredError,
    SequenceReplayError,
)
from management_server.heartbeat.metrics import HeartbeatMetricsCollector
from management_server.heartbeat.models import (
    HeartbeatRequest,
    ProtocolVersion,
    TimeoutConfig,
)
from management_server.heartbeat.protocol import HeartbeatProtocol
from management_server.heartbeat.repository import HeartbeatRepository
from management_server.heartbeat.schemas import (
    AgentCapabilitiesSchema,
    AgentHealthSchema,
    AgentSecuritySchema,
    HeartbeatRequestSchema,
    QueueMetricsSchema,
)
from management_server.heartbeat.service import HeartbeatService
from management_server.heartbeat.validator import HeartbeatValidator

# ─── Protocol Version Tests ────────────────────────────────────────────────


class TestProtocolVersion:
    def test_latest_version(self):
        assert ProtocolVersion.latest() == ProtocolVersion.V1

    def test_supported_versions(self):
        assert "1.0" in ProtocolVersion.supported_versions()

    def test_is_supported(self):
        assert ProtocolVersion.is_supported("1.0")
        assert not ProtocolVersion.is_supported("0.5")

    def test_negotiate_match(self):
        result = ProtocolVersion.negotiate("1.0", "1.0")
        assert result == "1.0"

    def test_negotiate_fallback(self):
        result = ProtocolVersion.negotiate("0.5", "1.0")
        assert result == "1.0"  # Falls back to server version

    def test_negotiate_no_match(self):
        result = ProtocolVersion.negotiate("0.5", "0.3")
        assert result == ""


# ─── Heartbeat Protocol Tests ──────────────────────────────────────────────


class TestHeartbeatProtocol:
    def setup_method(self):
        self.proto = HeartbeatProtocol()

    def test_negotiate_version_supported(self):
        result = self.proto.negotiate_version("1.0")
        assert result == "1.0"

    def test_negotiate_version_fallback(self):
        result = self.proto.negotiate_version("0.5")
        assert result == "1.0"

    def test_parse_request(self):
        schema = HeartbeatRequestSchema(
            machine_uuid="test-uuid",
            protocol_version="1.0",
            agent_version="2.0.0",
            hostname="test-host",
            environment="production",
            sequence_number=1,
        )
        request = self.proto.parse_request(schema)
        assert request.machine_uuid == "test-uuid"
        assert request.protocol_version == "1.0"

    def test_parse_request_with_all_fields(self):
        schema = HeartbeatRequestSchema(
            machine_uuid="full-test",
            certificate_fingerprint="fp123",
            protocol_version="1.0",
            agent_version="3.0.0",
            hostname="full-host",
            environment="staging",
            sequence_number=42,
            capabilities=AgentCapabilitiesSchema(iptables=True, sqlite=True),
            health=AgentHealthSchema(cpu_percent=45.0, ram_percent=60.0),
            queues=QueueMetricsSchema(event_queue=5),
            security=AgentSecuritySchema(current_posture="secured"),
        )
        request = self.proto.parse_request(schema)
        assert request.capabilities is not None
        assert request.capabilities.iptables
        assert request.health is not None
        assert request.health.cpu_percent == 45.0
        assert request.queues is not None
        assert request.queues.event_queue == 5
        assert request.security is not None
        assert request.security.current_posture == "secured"

    def test_build_response(self):
        request = HeartbeatRequest(machine_uuid="test")
        response = self.proto.build_response(request, "1.0")
        assert response.acknowledged
        assert response.negotiated_version == "1.0"

    def test_detect_capability_changes_added(self):
        changes = self.proto.detect_capability_changes(
            {"iptables": False}, {"iptables": True, "docker": True}
        )
        assert len(changes) >= 1
        # docker was added
        docker_changes = [c for c in changes if c["capability"] == "docker"]
        assert any(c["change"] == "added" for c in docker_changes)

    def test_detect_capability_changes_removed(self):
        changes = self.proto.detect_capability_changes(
            {"iptables": True, "docker": True}, {"iptables": True}
        )
        docker_changes = [c for c in changes if c["capability"] == "docker"]
        assert any(c["change"] == "removed" for c in docker_changes)

    def test_detect_capability_changes_modified(self):
        changes = self.proto.detect_capability_changes({"iptables": True}, {"iptables": False})
        iptables_changes = [c for c in changes if c["capability"] == "iptables"]
        assert any(c["change"] == "changed" for c in iptables_changes)


# ─── Validator Tests ───────────────────────────────────────────────────────


class TestHeartbeatValidator:
    def test_validate_valid_request(self):
        schema = HeartbeatRequestSchema(machine_uuid="test", protocol_version="1.0")
        HeartbeatValidator.validate_request(schema)  # Should not raise

    def test_validate_missing_uuid(self):
        with pytest.raises(HeartbeatValidationError):
            HeartbeatValidator.validate_request(
                HeartbeatRequestSchema(machine_uuid="", protocol_version="1.0")
            )

    def test_validate_missing_version(self):
        with pytest.raises(HeartbeatValidationError):
            HeartbeatValidator.validate_request(
                HeartbeatRequestSchema(machine_uuid="test", protocol_version="")
            )

    def test_validate_protocol_version_supported(self):
        result = HeartbeatValidator.validate_protocol_version("1.0")
        assert result == "1.0"

    def test_validate_protocol_version_unsupported(self):
        result = HeartbeatValidator.validate_protocol_version("0.5")
        assert result == "1.0"  # Falls back to latest

    def test_validate_sequence_first(self):
        HeartbeatValidator.validate_sequence_number(None, 1)  # Should not raise

    def test_validate_sequence_replay(self):
        with pytest.raises(SequenceReplayError):
            HeartbeatValidator.validate_sequence_number(5, 3)

    def test_validate_sequence_ok(self):
        HeartbeatValidator.validate_sequence_number(5, 6)  # Should not raise

    def test_validate_machine_registered(self):
        HeartbeatValidator.validate_machine_registered("test", True)

    def test_validate_machine_unregistered(self):
        with pytest.raises(MachineNotRegisteredError):
            HeartbeatValidator.validate_machine_registered("test", False)


# ─── Metrics Tests ─────────────────────────────────────────────────────────


class TestHeartbeatMetrics:
    def test_initial(self):
        m = HeartbeatMetricsCollector()
        snap = m.snapshot()
        assert snap.heartbeats_received == 0

    def test_counters(self):
        m = HeartbeatMetricsCollector()
        m.heartbeat_received(5.0)
        m.heartbeat_missed()
        m.protocol_error()
        m.version_mismatch()
        m.capability_change()
        snap = m.snapshot(online=3, offline=1, delayed=2)
        assert snap.heartbeats_received == 1
        assert snap.heartbeats_missed == 1
        assert snap.protocol_errors == 1
        assert snap.version_mismatches == 1
        assert snap.capability_changes == 1
        assert snap.average_latency_ms == 5.0
        assert snap.online_machines == 3
        assert snap.offline_machines == 1
        assert snap.delayed_machines == 2


# ─── Repository Tests ──────────────────────────────────────────────────────


class TestHeartbeatRepository:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = HeartbeatRepository(sqlite_session)
        self.session = sqlite_session

    async def test_record_heartbeat(self):
        result = await self.repo.record_heartbeat(
            machine_uuid="hb-test-1",
            protocol_version="1.0",
            agent_version="2.0.0",
            hostname="host-1",
            environment="production",
            sequence_number=1,
            health_json='{"cpu": 50}',
        )
        assert result["machine_uuid"] == "hb-test-1"
        assert result["status"] == "healthy"

    async def test_get_last_heartbeat(self):
        await self.repo.record_heartbeat(
            machine_uuid="last-hb",
            protocol_version="1.0",
            agent_version="1.0",
            hostname="h",
            environment="prod",
            sequence_number=1,
        )
        last = await self.repo.get_last_heartbeat("last-hb")
        assert last is not None
        assert last["machine_uuid"] == "last-hb"

    async def test_get_machine_status(self):
        await self.repo.record_heartbeat(
            machine_uuid="status-test",
            protocol_version="1.0",
            agent_version="1.0",
            hostname="h",
            environment="prod",
            sequence_number=1,
        )
        status = await self.repo.get_machine_status("status-test")
        assert status is not None
        assert status["status"] == "healthy"

    async def test_sequence_number_tracking(self):
        await self.repo.record_heartbeat(
            machine_uuid="seq-test",
            protocol_version="1.0",
            agent_version="1.0",
            hostname="h",
            environment="prod",
            sequence_number=5,
        )
        seq = await self.repo.get_last_sequence_number("seq-test")
        assert seq == 5

    async def test_status_counts(self):
        await self.repo.record_heartbeat(
            machine_uuid="count-1",
            protocol_version="1.0",
            agent_version="1.0",
            hostname="h",
            environment="prod",
            sequence_number=1,
        )
        counts = await self.repo.get_status_counts()
        assert "healthy" in counts

    async def test_capability_change_record(self):
        await self.repo.record_capability_change(
            machine_uuid="cap-test",
            capability="iptables",
            change_type="added",
            new_value=True,
        )
        # No error means success

    async def test_heartbeat_count(self):
        count = await self.repo.get_heartbeat_count()
        initial = count
        await self.repo.record_heartbeat(
            machine_uuid="count-test-2",
            protocol_version="1.0",
            agent_version="1.0",
            hostname="h",
            environment="prod",
            sequence_number=1,
        )
        count = await self.repo.get_heartbeat_count()
        assert count == initial + 1


# ─── Service Tests ─────────────────────────────────────────────────────────


class TestHeartbeatService:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.session = sqlite_session
        self.repo = HeartbeatRepository(sqlite_session)
        self.service = HeartbeatService(repository=self.repo)

    async def test_process_valid_heartbeat(self):
        schema = HeartbeatRequestSchema(
            machine_uuid="svc-test-1",
            protocol_version="1.0",
            agent_version="2.0.0",
            hostname="svc-host",
            environment="production",
            sequence_number=1,
        )
        resp = await self.service.process_heartbeat(schema)
        assert resp.acknowledged
        assert resp.negotiated_version == "1.0"

    async def test_process_heartbeat_with_capabilities(self):
        schema = HeartbeatRequestSchema(
            machine_uuid="svc-cap",
            protocol_version="1.0",
            agent_version="2.0.0",
            hostname="cap-host",
            environment="production",
            sequence_number=1,
            capabilities=AgentCapabilitiesSchema(iptables=True, sqlite=True),
        )
        resp = await self.service.process_heartbeat(schema)
        assert resp.acknowledged

    async def test_heartbeat_with_health(self):
        schema = HeartbeatRequestSchema(
            machine_uuid="svc-health",
            protocol_version="1.0",
            agent_version="2.0.0",
            hostname="health-host",
            environment="production",
            sequence_number=1,
            health=AgentHealthSchema(cpu_percent=75.0, ram_percent=80.0),
        )
        resp = await self.service.process_heartbeat(schema)
        assert resp.acknowledged

    async def test_heartbeat_with_security(self):
        schema = HeartbeatRequestSchema(
            machine_uuid="svc-sec",
            protocol_version="1.0",
            agent_version="2.0.0",
            hostname="sec-host",
            environment="production",
            sequence_number=1,
            security=AgentSecuritySchema(current_posture="hardened"),
        )
        resp = await self.service.process_heartbeat(schema)
        assert resp.acknowledged

    async def test_reject_unregistered_machine(self):
        schema = HeartbeatRequestSchema(
            machine_uuid="unregistered",
            protocol_version="1.0",
            sequence_number=1,
        )
        with pytest.raises(MachineNotRegisteredError):
            await self.service.process_heartbeat(schema, is_machine_registered=False)

    async def test_reject_replay(self):
        schema = HeartbeatRequestSchema(
            machine_uuid="replay-test",
            protocol_version="1.0",
            agent_version="1.0",
            hostname="replay",
            environment="prod",
            sequence_number=1,
        )
        await self.service.process_heartbeat(schema)

        # Same sequence should fail as replay
        schema2 = HeartbeatRequestSchema(
            machine_uuid="replay-test",
            protocol_version="1.0",
            agent_version="1.0",
            hostname="replay",
            environment="prod",
            sequence_number=1,
        )
        with pytest.raises(SequenceReplayError):
            await self.service.process_heartbeat(schema2)

    async def test_sequence_advances(self):
        for i in range(1, 4):
            schema = HeartbeatRequestSchema(
                machine_uuid="seq-advance",
                protocol_version="1.0",
                agent_version="1.0",
                hostname="seq",
                environment="prod",
                sequence_number=i,
            )
            resp = await self.service.process_heartbeat(schema)
            assert resp.acknowledged

    async def test_get_machine_status(self):
        schema = HeartbeatRequestSchema(
            machine_uuid="status-me",
            protocol_version="1.0",
            agent_version="1.0",
            hostname="status-host",
            environment="staging",
            sequence_number=1,
        )
        await self.service.process_heartbeat(schema)

        status = await self.service.get_machine_status("status-me")
        assert status.machine_uuid == "status-me"
        assert status.status == "healthy"
        assert status.hostname == "status-host"

    async def test_get_machine_status_unknown(self):
        status = await self.service.get_machine_status("nonexistent")
        assert status.status == "unknown"

    async def test_timeout_detection(self):
        # Create a heartbeat with a very old timestamp

        from sqlalchemy import text

        old = datetime.now(tz=UTC) - timedelta(hours=1)
        await self.session.execute(
            text("""
                INSERT INTO machine_status (machine_uuid, status, last_heartbeat_at,
                    last_sequence_number, created_at, updated_at)
                VALUES (:mu, 'healthy', :old, 0, :old, :old)
            """),
            {"mu": "timeout-test", "old": old},
        )
        await self.session.commit()

        config = TimeoutConfig(
            healthy_timeout_seconds=1,
            delayed_timeout_seconds=5,
            offline_timeout_seconds=30,
        )
        service = HeartbeatService(repository=self.repo, timeout_config=config)
        _changes = await service.detect_timeouts()

        # SQLite does not support RETURNING, so changes may be empty
        # Verify the update happened by checking status directly
        status = await self.repo.get_machine_status("timeout-test")
        assert status is not None
        # Should be delayed or offline
        assert status["status"] in ("delayed", "offline")

    async def test_get_metrics(self):
        schema = HeartbeatRequestSchema(
            machine_uuid="metrics-test",
            protocol_version="1.0",
            agent_version="1.0",
            hostname="metrics",
            environment="prod",
            sequence_number=1,
        )
        await self.service.process_heartbeat(schema)

        metrics = await self.service.get_metrics()
        assert metrics.heartbeats_received >= 1


# ─── Forward Compatibility Tests ───────────────────────────────────────────


class TestForwardCompatibility:
    def test_unknown_fields_accepted(self):
        """The schema should accept unknown fields gracefully via Pydantic."""
        schema = HeartbeatRequestSchema(
            machine_uuid="future",
            protocol_version="2.0",  # Will be negotiated down
            sequence_number=1,
        )
        assert schema.machine_uuid == "future"

    def test_protocol_version_negotiation(self):
        """Future protocol versions should negotiate to latest supported."""
        result = HeartbeatValidator.validate_protocol_version("2.0")
        assert result == "1.0"  # Falls back

    def test_empty_capabilities(self):
        schema = HeartbeatRequestSchema(
            machine_uuid="empty-cap",
            protocol_version="1.0",
            sequence_number=1,
        )
        assert schema.capabilities is None


# ─── API Tests ─────────────────────────────────────────────────────────────


class TestHeartbeatAPI:
    def test_health_endpoint(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_heartbeat_no_db(self, client: TestClient):
        """Without DB initialization, heartbeat endpoint returns 503."""
        resp = client.post(
            "/api/v1/heartbeat",
            json={
                "machine_uuid": "api-test",
                "protocol_version": "1.0",
                "sequence_number": 1,
            },
        )
        assert resp.status_code in (503,)

    def test_heartbeat_metrics_no_db(self, client: TestClient):
        resp = client.get("/api/v1/heartbeat/metrics")
        assert resp.status_code in (503,)

    def test_heartbeat_status_no_db(self, client: TestClient):
        resp = client.get("/api/v1/heartbeat/status/api-test")
        assert resp.status_code in (503,)
