"""
Comprehensive tests for the Certificate Authority subsystem.

All tests use ephemeral keys — never production keys.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.certificates.authority import CertificateAuthority
from management_server.certificates.exceptions import AuthorityError
from management_server.certificates.lifecycle import RenewalScheduler
from management_server.certificates.manager import CertificateManager
from management_server.certificates.models import (
    CAInfo,
    CertificateStatus,
    MachineCertificate,
)
from management_server.certificates.store import CertificateStore
from management_server.certificates.validator import CertificateValidator
from management_server.machines.identity import MachineIdentity


class TestCAInfo:
    def test_ca_info_creation(self):
        ca = CAInfo(subject="CN=Test", fingerprint="abc123", serial="1")
        assert ca.subject == "CN=Test"
        assert ca.fingerprint == "abc123"
        assert ca.is_root

    def test_ca_info_frozen(self):
        ca = CAInfo()
        with pytest.raises(AttributeError):
            ca.subject = "modified"  # type: ignore[misc]


class TestMachineCertificate:
    def test_is_expired(self):
        past = datetime(2020, 1, 1, tzinfo=UTC)
        cert = MachineCertificate(expires_at=past)
        assert cert.is_expired

    def test_is_not_expired(self):
        future = datetime(2099, 1, 1, tzinfo=UTC)
        cert = MachineCertificate(expires_at=future)
        assert not cert.is_expired

    def test_days_until_expiry(self):
        from datetime import timedelta

        future = datetime.now(tz=UTC) + timedelta(days=30)
        cert = MachineCertificate(expires_at=future)
        assert 29 <= cert.days_until_expiry <= 30

    def test_is_revoked(self):
        cert = MachineCertificate(status=CertificateStatus.REVOKED)
        assert cert.is_revoked


class TestRootCA:
    async def test_root_ca_generation(self, sqlite_session: AsyncSession):
        store = CertificateStore(sqlite_session)
        ca = CertificateAuthority(store)
        ca_info = await ca.initialize()

        assert ca_info is not None
        assert ca_info.is_initialized
        assert "AI Security Management Root CA" in ca_info.subject
        assert ca_info.fingerprint != ""
        assert ca.is_initialized

    async def test_root_ca_persists(self, sqlite_session: AsyncSession):
        store = CertificateStore(sqlite_session)
        ca = CertificateAuthority(store)
        await ca.initialize()

        # Re-load from DB
        ca2 = CertificateAuthority(store)
        ca_info2 = await ca2.initialize()
        assert ca_info2 is not None
        assert ca_info2.is_initialized


class TestCertificateIssuance:
    async def test_issue_machine_certificate(self, sqlite_session: AsyncSession):
        store = CertificateStore(sqlite_session)
        ca = CertificateAuthority(store)
        await ca.initialize()

        priv = ed25519.Ed25519PrivateKey.generate()
        pub_pem = (
            priv.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )

        cert = ca.issue_machine_certificate(
            machine_uuid="test-uuid-123",
            public_key_pem=pub_pem,
            hostname="test-server",
        )
        assert cert.machine_uuid == "test-uuid-123"
        assert cert.subject == "test-server"
        assert cert.certificate_fingerprint != ""
        assert cert.status == CertificateStatus.ACTIVE

    async def test_issue_without_ca_raises(self, sqlite_session: AsyncSession):
        store = CertificateStore(sqlite_session)
        ca = CertificateAuthority(store)
        with pytest.raises(AuthorityError):
            ca.issue_machine_certificate("uuid", "invalid_key")


class TestValidator:
    async def test_validate_valid_certificate(self, sqlite_session: AsyncSession):
        store = CertificateStore(sqlite_session)
        ca = CertificateAuthority(store)
        await ca.initialize()

        priv = ed25519.Ed25519PrivateKey.generate()
        pub_pem = (
            priv.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )

        cert = ca.issue_machine_certificate("test-uuid", pub_pem)

        validator = CertificateValidator(ca.ca_cert_pem)
        result = validator.validate(cert)
        assert result.valid

    async def test_validate_expired_certificate(self, sqlite_session: AsyncSession):
        store = CertificateStore(sqlite_session)
        ca = CertificateAuthority(store)
        await ca.initialize()

        past = datetime(2020, 1, 1, tzinfo=UTC)
        cert = MachineCertificate(
            machine_uuid="test-uuid",
            certificate_pem="",
            public_key_pem="",
            expires_at=past,
        )

        validator = CertificateValidator(ca.ca_cert_pem)
        result = validator.validate(cert)
        assert not result.valid

    async def test_validate_revoked_certificate(self, sqlite_session: AsyncSession):  # noqa: ARG002
        cert = MachineCertificate(
            machine_uuid="test-uuid",
            certificate_pem="",
            public_key_pem="",
            status=CertificateStatus.REVOKED,
        )
        validator = CertificateValidator("")
        result = validator.validate(cert)
        assert not result.valid

    def test_verify_self_signed(self):
        import datetime

        from cryptography import x509
        from cryptography.x509.oid import NameOID

        key = ed25519.Ed25519PrivateKey.generate()
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, "Test CA"),
            ]
        )
        now = datetime.datetime.now(datetime.UTC)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(1)
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=1))
            .sign(key, None)
        )
        pem = cert.public_bytes(serialization.Encoding.PEM).decode()
        assert CertificateValidator.verify_self_signed(pem)


class TestLifecycle:
    def test_renewal_scheduling(self):
        sched = RenewalScheduler()
        assert sched.get_renewal_info(90).action_required == "none"
        assert sched.get_renewal_info(20).action_required == "renew_soon"
        assert sched.get_renewal_info(7).action_required == "renew_now"
        assert sched.get_renewal_info(-1).action_required == "expired"


class TestMachineIdentity:
    def test_machine_identity_creation(self):
        ident = MachineIdentity(
            machine_uuid="uuid-123",
            hostname="server-01",
            environment="production",
        )
        assert ident.machine_uuid == "uuid-123"
        assert ident.hostname == "server-01"

    def test_machine_identity_frozen(self):
        ident = MachineIdentity()
        with pytest.raises(AttributeError):
            ident.hostname = "modified"  # type: ignore[misc]


class TestCertificateStore:
    async def test_save_and_retrieve(self, sqlite_session: AsyncSession):
        store = CertificateStore(sqlite_session)

        cert = MachineCertificate(
            machine_uuid="test-uuid",
            serial="12345",
            certificate_pem="pem-data",
            public_key_pem="key-data",
            certificate_fingerprint="fp1",
            public_key_fingerprint="fp2",
        )
        await store.save_certificate(cert)

        retrieved = await store.get_certificate("test-uuid")
        assert retrieved is not None
        assert retrieved.machine_uuid == "test-uuid"
        assert retrieved.serial == "12345"

    async def test_revoke(self, sqlite_session: AsyncSession):
        store = CertificateStore(sqlite_session)

        cert = MachineCertificate(
            machine_uuid="revoke-uuid",
            serial="999",
            certificate_pem="pem",
            public_key_pem="key",
            certificate_fingerprint="fp",
            public_key_fingerprint="fp",
        )
        await store.save_certificate(cert)
        await store.revoke_certificate("revoke-uuid", "test revocation")

        retrieved = await store.get_certificate("revoke-uuid")
        assert retrieved is not None
        assert retrieved.is_revoked

    async def test_crl(self, sqlite_session: AsyncSession):
        store = CertificateStore(sqlite_session)
        cert = MachineCertificate(
            machine_uuid="crl-uuid",
            serial="1",
            certificate_pem="p",
            public_key_pem="k",
            certificate_fingerprint="f",
            public_key_fingerprint="f",
            status=CertificateStatus.REVOKED,
        )
        await store.save_certificate(cert)
        crl = await store.get_crl()
        assert len(crl) >= 1


class TestCertificateManager:
    async def test_manager_initialize(self, sqlite_session: AsyncSession):
        store = CertificateStore(sqlite_session)
        mgr = CertificateManager(store)
        await mgr.initialize()
        assert mgr.is_initialized

    async def test_manager_issue_and_validate(self, sqlite_session: AsyncSession):
        store = CertificateStore(sqlite_session)
        mgr = CertificateManager(store)
        await mgr.initialize()

        priv = ed25519.Ed25519PrivateKey.generate()
        pub_pem = (
            priv.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )

        cert = await mgr.issue_certificate("mgmt-uuid", pub_pem)
        result = await mgr.validate_certificate(cert)
        assert result.valid

    async def test_manager_revoke(self, sqlite_session: AsyncSession):
        store = CertificateStore(sqlite_session)
        mgr = CertificateManager(store)
        await mgr.initialize()

        priv = ed25519.Ed25519PrivateKey.generate()
        pub_pem = (
            priv.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )

        await mgr.issue_certificate("rev-mgmt", pub_pem)
        await mgr.revoke_certificate("rev-mgmt", "testing")

        crl = await mgr.get_crl()
        assert any(r.get("machine_uuid") == "rev-mgmt" for r in crl)


class TestBenchmarks:
    @pytest.mark.benchmark
    def test_key_generation(self):
        import time

        n = 100
        t = time.monotonic()
        for _ in range(n):
            ed25519.Ed25519PrivateKey.generate()
        elapsed = time.monotonic() - t
        print(f"\n  Key generation: {n / elapsed:.0f} keys/s ({n} in {elapsed:.3f}s)")

    @pytest.mark.benchmark
    async def test_certificate_issuance(self, sqlite_session: AsyncSession):
        store = CertificateStore(sqlite_session)
        ca = CertificateAuthority(store)
        await ca.initialize()

        priv = ed25519.Ed25519PrivateKey.generate()
        pub_pem = (
            priv.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )

        n = 50
        import time

        t = time.monotonic()
        for _ in range(n):
            ca.issue_machine_certificate("bench-uuid", pub_pem)
        elapsed = time.monotonic() - t
        print(f"\n  Issuance: {n / elapsed:.0f} certs/s ({n} in {elapsed:.3f}s)")
