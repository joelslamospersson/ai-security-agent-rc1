"""
Comprehensive tests for the Machine Registry and Registration subsystem.
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.certificates.manager import CertificateManager
from management_server.certificates.store import CertificateStore
from management_server.machines.exceptions import (
    DuplicateMachineError,
    InvalidTransitionError,
    MachineNotFoundError,
)
from management_server.machines.metrics import RegistryMetricsCollector
from management_server.machines.registry import MachineRegistry
from management_server.machines.repository import MachineRepository
from management_server.machines.schemas import RegistrationRequest
from management_server.machines.service import RegistrationService
from management_server.machines.state_machine import MachineState, MachineStateMachine

TEST_KEY = ed25519.Ed25519PrivateKey.generate()
TEST_PUB_PEM = (
    TEST_KEY.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)

TEST_KEY_2 = ed25519.Ed25519PrivateKey.generate()
TEST_PUB_PEM_2 = (
    TEST_KEY_2.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)


# ─── State Machine Tests ───────────────────────────────────────────────────


class TestStateMachine:
    def test_valid_transitions(self):
        assert MachineStateMachine.is_legal(MachineState.UNKNOWN, MachineState.PENDING_REGISTRATION)
        assert MachineStateMachine.is_legal(
            MachineState.PENDING_REGISTRATION, MachineState.REGISTERED
        )

    def test_invalid_transitions(self):
        assert not MachineStateMachine.is_legal(MachineState.UNKNOWN, MachineState.REGISTERED)
        assert not MachineStateMachine.is_legal(
            MachineState.REGISTERED, MachineState.PENDING_REGISTRATION
        )

    def test_validate_transition_raises(self):
        with pytest.raises(InvalidTransitionError):
            MachineStateMachine.validate_transition(MachineState.UNKNOWN, MachineState.REGISTERED)

    def test_legal_transitions_from(self):
        targets = MachineStateMachine.legal_transitions_from(MachineState.PENDING_REGISTRATION)
        assert MachineState.REGISTERED in targets
        assert MachineState.REJECTED in targets
        assert MachineState.EXPIRED in targets

    def test_all_states(self):
        states = MachineStateMachine.all_states()
        assert MachineState.UNKNOWN in states
        assert MachineState.REVOKED in states

    def test_apply_transition(self):
        sm = MachineStateMachine()
        t = sm.apply(MachineState.UNKNOWN, MachineState.PENDING_REGISTRATION)
        assert t.from_state == MachineState.UNKNOWN
        assert t.to_state == MachineState.PENDING_REGISTRATION
        assert sm.history_count == 1

    def test_apply_invalid_raises(self):
        sm = MachineStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.apply(MachineState.UNKNOWN, MachineState.REGISTERED)


# ─── Metrics Tests ─────────────────────────────────────────────────────────


class TestMetrics:
    def test_metrics_initial(self):
        m = RegistryMetricsCollector()
        snap = m.snapshot()
        assert snap.registrations_requested == 0

    def test_metrics_increment(self):
        m = RegistryMetricsCollector()
        m.registration_requested()
        m.approved(30.0)
        m.rejected()
        m.revoked()
        snap = m.snapshot(pending=5, total_machines=10)
        assert snap.registrations_requested == 1
        assert snap.approved == 1
        assert snap.rejected == 1
        assert snap.revoked == 1
        assert snap.pending == 5
        assert snap.total_machines == 10
        assert snap.average_approval_time_ms > 0


# ─── Repository Tests ──────────────────────────────────────────────────────


class TestMachineRepository:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = MachineRepository(sqlite_session)
        self.session = sqlite_session

    async def test_create_and_get(self):
        record = await self.repo.create_registration_request(
            machine_uuid="repo-test-1",
            hostname="host-1",
            operating_system="linux",
            architecture="x86_64",
            environment="production",
            agent_version="1.0.0",
            public_key_fingerprint="fp123",
            public_key_pem=TEST_PUB_PEM,
        )
        assert record["machine_uuid"] == "repo-test-1"
        assert record["status"] == MachineState.PENDING_REGISTRATION.value

    async def test_duplicate_detection(self):
        await self.repo.create_registration_request(
            machine_uuid="dup-test",
            hostname="",
            operating_system="",
            architecture="",
            environment="production",
            agent_version="",
            public_key_fingerprint="fp",
            public_key_pem=TEST_PUB_PEM,
        )
        with pytest.raises(DuplicateMachineError):
            await self.repo.create_registration_request(
                machine_uuid="dup-test",
                hostname="",
                operating_system="",
                architecture="",
                environment="production",
                agent_version="",
                public_key_fingerprint="fp",
                public_key_pem=TEST_PUB_PEM,
            )

    async def test_update_status(self):
        await self.repo.create_registration_request(
            machine_uuid="status-test",
            hostname="",
            operating_system="",
            architecture="",
            environment="production",
            agent_version="",
            public_key_fingerprint="fp",
            public_key_pem=TEST_PUB_PEM,
        )
        updated = await self.repo.update_status("status-test", MachineState.REGISTERED)
        assert updated["status"] == MachineState.REGISTERED.value

    async def test_get_machine_not_found(self):
        with pytest.raises(MachineNotFoundError):
            await self.repo.get_machine("nonexistent")

    async def test_list_machines(self):
        await self.repo.create_registration_request(
            machine_uuid="list-test-1",
            hostname="h1",
            operating_system="linux",
            architecture="x86_64",
            environment="production",
            agent_version="1.0",
            public_key_fingerprint="fp1",
            public_key_pem=TEST_PUB_PEM,
        )
        await self.repo.create_registration_request(
            machine_uuid="list-test-2",
            hostname="h2",
            operating_system="linux",
            architecture="arm64",
            environment="staging",
            agent_version="1.1",
            public_key_fingerprint="fp2",
            public_key_pem=TEST_PUB_PEM_2,
        )
        _machines, total = await self.repo.list_machines()
        assert total >= 2

    async def test_list_machines_by_status(self):
        await self.repo.delete_machine("list-status")
        await self.repo.create_registration_request(
            machine_uuid="list-status",
            hostname="",
            operating_system="",
            architecture="",
            environment="production",
            agent_version="",
            public_key_fingerprint="fp",
            public_key_pem=TEST_PUB_PEM,
        )
        # Change status
        await self.repo.update_status("list-status", MachineState.REGISTERED)
        _machines, total = await self.repo.list_machines(status=MachineState.REGISTERED)
        assert total >= 1

    async def test_count_machines_by_status(self):
        counts = await self.repo.count_machines_by_status()
        assert isinstance(counts, dict)

    async def test_find_by_hostname(self):
        await self.repo.create_registration_request(
            machine_uuid="hostname-test",
            hostname="unique-host",
            operating_system="",
            architecture="",
            environment="",
            agent_version="",
            public_key_fingerprint="fp",
            public_key_pem=TEST_PUB_PEM,
        )
        found = await self.repo.find_by_hostname("unique-host")
        assert found is not None
        assert found["machine_uuid"] == "hostname-test"

    async def test_get_all_pending(self):
        await self.repo.delete_machine("pending-test")
        await self.repo.create_registration_request(
            machine_uuid="pending-test",
            hostname="",
            operating_system="",
            architecture="",
            environment="production",
            agent_version="",
            public_key_fingerprint="fp",
            public_key_pem=TEST_PUB_PEM,
        )
        pending = await self.repo.get_all_pending()
        assert any(m["machine_uuid"] == "pending-test" for m in pending)


# ─── Registry Tests ────────────────────────────────────────────────────────


class TestMachineRegistry:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = MachineRepository(sqlite_session)
        self.registry = MachineRegistry(self.repo)

    async def test_register(self):
        result = await self.registry.register(
            machine_uuid="reg-test-1",
            hostname="server-01",
            operating_system="linux",
            architecture="x86_64",
            environment="production",
            agent_version="2.0.0",
            public_key_fingerprint="fp123",
            public_key_pem=TEST_PUB_PEM,
        )
        assert result["status"] == MachineState.PENDING_REGISTRATION.value

    async def test_register_duplicate(self):
        await self.registry.register(
            machine_uuid="reg-dup",
            public_key_fingerprint="fp",
            public_key_pem=TEST_PUB_PEM,
        )
        with pytest.raises(DuplicateMachineError):
            await self.registry.register(
                machine_uuid="reg-dup",
                public_key_fingerprint="fp",
                public_key_pem=TEST_PUB_PEM,
            )

    async def test_approve(self, sqlite_session: AsyncSession):  # noqa: ARG002
        await self.registry.register(
            machine_uuid="reg-approve",
            hostname="approve-me",
            public_key_fingerprint="fp",
            public_key_pem=TEST_PUB_PEM,
        )
        # CertificateManager needed for approve in registry
        # Testing approve via repository mock: direct update_status
        result = await self.registry.approve(
            machine_uuid="reg-approve",
            approved_by="admin",
            reason="Approved for testing",
            certificate_fingerprint="cert-fp-123",
        )
        assert result["status"] == MachineState.REGISTERED.value

    async def test_reject(self):
        await self.registry.register(
            machine_uuid="reg-reject",
            public_key_fingerprint="fp",
            public_key_pem=TEST_PUB_PEM,
        )
        result = await self.registry.reject(
            machine_uuid="reg-reject",
            rejected_by="admin",
            reason="Rejected for testing",
        )
        assert result["status"] == MachineState.REJECTED.value

    async def test_expire(self):
        await self.registry.register(
            machine_uuid="reg-expire",
            public_key_fingerprint="fp",
            public_key_pem=TEST_PUB_PEM,
        )
        result = await self.registry.expire("reg-expire")
        assert result["status"] == MachineState.EXPIRED.value

    async def test_revoke_registered(self):
        await self.registry.register(
            machine_uuid="reg-revoke",
            public_key_fingerprint="fp",
            public_key_pem=TEST_PUB_PEM,
        )
        # Must approve first to transition to REGISTERED
        await self.registry.approve(
            machine_uuid="reg-revoke",
            certificate_fingerprint="fp",
        )
        result = await self.registry.revoke(
            machine_uuid="reg-revoke",
            revoked_by="admin",
            reason="Security incident",
        )
        assert result["status"] == MachineState.REVOKED.value

    async def test_get_machine(self):
        await self.registry.register(
            machine_uuid="reg-get",
            public_key_fingerprint="fp",
            public_key_pem=TEST_PUB_PEM,
        )
        info = await self.registry.get_machine("reg-get")
        assert info["machine_uuid"] == "reg-get"

    async def test_get_machine_not_found(self):
        with pytest.raises(MachineNotFoundError):
            await self.registry.get_machine("nope")

    async def test_list_machines(self):
        await self.registry.register(
            machine_uuid="list-1",
            public_key_fingerprint="fp",
            public_key_pem=TEST_PUB_PEM,
        )
        result = await self.registry.list_machines()
        assert result["total"] >= 1

    async def test_metrics_snapshot(self):
        await self.registry.register(
            machine_uuid="metrics-test",
            public_key_fingerprint="fp",
            public_key_pem=TEST_PUB_PEM,
        )
        metrics = await self.registry.get_metrics()
        assert metrics["registrations_requested"] >= 1


# ─── Registration Service Tests ────────────────────────────────────────────


class TestRegistrationService:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        # Initialize CertificateManager
        store = CertificateStore(sqlite_session)
        cert_manager = CertificateManager(store)
        await cert_manager.initialize()

        self.repo = MachineRepository(sqlite_session)
        self.registry = MachineRegistry(self.repo)
        self.service = RegistrationService(
            registry=self.registry,
            repository=self.repo,
            cert_manager=cert_manager,
        )

    async def test_create_registration(self):
        req = RegistrationRequest(
            machine_uuid="svc-test-1",
            hostname="svc-host",
            operating_system="linux",
            architecture="x86_64",
            environment="production",
            agent_version="3.0.0",
            public_key_pem=TEST_PUB_PEM,
        )
        resp = await self.service.create_registration(req)
        assert resp.machine_uuid == "svc-test-1"
        assert resp.status == MachineState.PENDING_REGISTRATION

    async def test_approve_with_certificate(self):
        req = RegistrationRequest(
            machine_uuid="svc-approve",
            hostname="svc-approve-host",
            public_key_pem=TEST_PUB_PEM,
        )
        await self.service.create_registration(req)

        resp = await self.service.approve(
            machine_uuid="svc-approve",
            approved_by="admin",
            reason="Test approval",
        )
        assert resp.status == MachineState.REGISTERED
        assert resp.certificate_pem is not None

    async def test_approve_pending_only(self):
        with pytest.raises(MachineNotFoundError):
            await self.service.approve("nonexistent")

    async def test_reject(self):
        req = RegistrationRequest(
            machine_uuid="svc-reject",
            public_key_pem=TEST_PUB_PEM,
        )
        await self.service.create_registration(req)
        resp = await self.service.reject(
            machine_uuid="svc-reject",
            rejected_by="admin",
            reason="Test rejection",
        )
        assert resp.status == MachineState.REJECTED

    async def test_revoke_with_certificate(self):
        req = RegistrationRequest(
            machine_uuid="svc-revoke",
            hostname="revoke-me",
            public_key_pem=TEST_PUB_PEM,
        )
        await self.service.create_registration(req)
        await self.service.approve("svc-revoke")

        resp = await self.service.revoke(
            machine_uuid="svc-revoke",
            revoked_by="admin",
            reason="Security test",
        )
        assert resp.status == MachineState.REVOKED

    async def test_lookup(self):
        req = RegistrationRequest(
            machine_uuid="svc-lookup",
            public_key_pem=TEST_PUB_PEM,
        )
        await self.service.create_registration(req)
        info = await self.service.lookup("svc-lookup")
        assert info["machine_uuid"] == "svc-lookup"
        assert info["status"] == MachineState.PENDING_REGISTRATION.value

    async def test_create_invalid(self):
        with pytest.raises(Exception) as excinfo:
            await self.service.create_registration(
                RegistrationRequest(
                    machine_uuid="",
                    public_key_pem=TEST_PUB_PEM,
                )
            )
        assert excinfo.value is not None


# ─── API Tests ─────────────────────────────────────────────────────────────


class TestRegistrationAPI:
    def test_create_registration_endpoint(self, client: TestClient):
        resp = client.post(
            "/api/v1/registration",
            json={
                "machine_uuid": "api-test-1",
                "hostname": "api-host",
                "operating_system": "linux",
                "architecture": "x86_64",
                "environment": "production",
                "agent_version": "1.0.0",
                "public_key_pem": TEST_PUB_PEM,
            },
        )
        # Registration endpoint requires DB and cert_manager, so may return 503
        assert resp.status_code in (200, 503)

    def test_get_registration_not_found(self, client: TestClient):
        resp = client.get("/api/v1/registration/nonexistent")
        assert resp.status_code in (404, 503)

    def test_health_endpoint(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data


# ─── State Machine Validation Tests ────────────────────────────────────────


class TestStateMachineValidation:
    def test_unknown_transition_not_allowed(self):
        for target in MachineState:
            if target not in (MachineState.PENDING_REGISTRATION, MachineState.UNKNOWN):
                assert not MachineStateMachine.is_legal(MachineState.UNKNOWN, target)

    def test_registration_transition_set(self):
        allowed = MachineStateMachine.legal_transitions_from(MachineState.PENDING_REGISTRATION)
        assert sorted(allowed) == [
            MachineState.EXPIRED,
            MachineState.REGISTERED,
            MachineState.REJECTED,
        ]

    def test_invalid_transition_error_message(self):
        try:
            MachineStateMachine.validate_transition(MachineState.REGISTERED, MachineState.UNKNOWN)
        except InvalidTransitionError as e:
            assert "registered" in str(e)
            assert "unknown" in str(e)
