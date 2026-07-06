"""
Comprehensive tests for the Configuration Synchronization Framework.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.configsync.exceptions import (
    IntegrityError,
    InvalidTransitionError,
    VersionMismatchError,
)
from management_server.configsync.lifecycle import PackageLifecycle
from management_server.configsync.metrics import ConfigSyncMetricsCollector
from management_server.configsync.models import (
    ConfigurationPackage,
    PackageFormat,
    PackageState,
    PackageType,
)
from management_server.configsync.repository import ConfigSyncRepository
from management_server.configsync.service import ConfigSyncService
from management_server.configsync.validator import PackageValidator

# ─── Model Tests ──────────────────────────────────────────────────────────


class TestConfigurationPackage:
    def test_create(self):
        pkg = ConfigurationPackage.create(
            package_type="configuration",
            version="2",
            payload="config_data",
            metadata={"env": "production"},
        )
        assert pkg.package_id != ""
        assert pkg.package_type == PackageType.CONFIGURATION
        assert pkg.version == "2"
        assert pkg.checksum != ""

    def test_frozen(self):
        pkg = ConfigurationPackage.create("configuration", "1")
        with pytest.raises(AttributeError):
            pkg.package_id = "changed"  # type: ignore[misc]

    def test_integrity_verification(self):
        pkg = ConfigurationPackage.create("configuration", "1", payload="data")
        assert pkg.verify_integrity()

    def test_integrity_failure(self):
        pkg = ConfigurationPackage(
            package_id="test",
            package_type=PackageType.CONFIGURATION,
            checksum="wrong",
        )
        assert not pkg.verify_integrity()

    def test_to_dict(self):
        pkg = ConfigurationPackage.create("rules", "3", payload="rules_data")
        d = pkg.to_dict()
        assert d["package_type"] == "rules"
        assert d["version"] == "3"
        assert d["checksum"] == pkg.checksum

    def test_delta_package(self):
        pkg = ConfigurationPackage.create(
            package_type="configuration",
            version="2",
            format_type=PackageFormat.DELTA,
            base_package_id="base-123",
        )
        assert pkg.format == PackageFormat.DELTA
        assert pkg.base_package_id == "base-123"


# ─── Lifecycle Tests ──────────────────────────────────────────────────────


class TestPackageLifecycle:
    def test_legal_transitions(self):
        assert PackageLifecycle.is_legal(PackageState.CREATED, PackageState.SIGNED)
        assert PackageLifecycle.is_legal(PackageState.SIGNED, PackageState.PUBLISHED)
        assert PackageLifecycle.is_legal(PackageState.PUBLISHED, PackageState.AVAILABLE)

    def test_illegal_transitions(self):
        assert not PackageLifecycle.is_legal(PackageState.CREATED, PackageState.AVAILABLE)
        assert not PackageLifecycle.is_legal(PackageState.AVAILABLE, PackageState.CREATED)

    def test_validate_raises(self):
        with pytest.raises(InvalidTransitionError):
            PackageLifecycle.validate(PackageState.CREATED, PackageState.AVAILABLE)

    def test_full_lifecycle(self):
        transitions = [
            (PackageState.CREATED, PackageState.SIGNED),
            (PackageState.SIGNED, PackageState.PUBLISHED),
            (PackageState.PUBLISHED, PackageState.AVAILABLE),
            (PackageState.AVAILABLE, PackageState.SUPERSEDED),
            (PackageState.SUPERSEDED, PackageState.ARCHIVED),
        ]
        for from_s, to_s in transitions:
            assert PackageLifecycle.is_legal(from_s, to_s)


# ─── Validator Tests ──────────────────────────────────────────────────────


class TestPackageValidator:
    def test_valid_request(self):
        errors = PackageValidator.validate_new("configuration", "1", "payload")
        assert len(errors) == 0

    def test_missing_type(self):
        errors = PackageValidator.validate_new("", "1")
        assert any("package_type" in e for e in errors)

    def test_unknown_type(self):
        errors = PackageValidator.validate_new("unknown", "1")
        assert any("Unknown" in e for e in errors)

    def test_invalid_format(self):
        errors = PackageValidator.validate_new("configuration", "1", format_type="invalid")
        assert any("Invalid format" in e for e in errors)

    def test_integrity_check_pass(self):
        pkg = ConfigurationPackage.create("configuration", "1", "data")
        PackageValidator.verify_integrity(pkg)  # Should not raise

    def test_integrity_check_fail(self):
        pkg = ConfigurationPackage(
            package_id="test",
            package_type=PackageType.CONFIGURATION,
            checksum="wrong",
        )
        with pytest.raises(IntegrityError):
            PackageValidator.verify_integrity(pkg)

    def test_version_compatibility(self):
        pkg = ConfigurationPackage.create("configuration", "1", minimum_agent_version="2.0.0")
        PackageValidator.verify_agent_compatibility(pkg, "2.0.0")  # OK
        with pytest.raises(VersionMismatchError):
            PackageValidator.verify_agent_compatibility(pkg, "1.0.0")

    def test_get_available_for_agent(self):
        pkg1 = ConfigurationPackage.create("configuration", "2")
        _pkg1_c = ConfigurationPackage(
            package_id=pkg1.package_id,
            package_type=pkg1.package_type,
            version=pkg1.version,
            state=PackageState.AVAILABLE,
            checksum=pkg1.checksum,
        )
        pkg2 = ConfigurationPackage.create("configuration", "1")
        _pkg2_c = ConfigurationPackage(
            package_id=pkg2.package_id,
            package_type=pkg2.package_type,
            version=pkg2.version,
            state=PackageState.AVAILABLE,
            checksum=pkg2.checksum,
        )
        # Override states
        pkg1 = ConfigurationPackage(
            package_id=pkg1.package_id,
            package_type=pkg1.package_type,
            version=pkg1.version,
            state=PackageState.AVAILABLE,
            checksum=pkg1.checksum,
        )
        pkg2 = ConfigurationPackage(
            package_id=pkg2.package_id,
            package_type=pkg2.package_type,
            version=pkg2.version,
            state=PackageState.AVAILABLE,
            checksum=pkg2.checksum,
        )
        available = PackageValidator.get_available_for_agent(
            [pkg1, pkg2],
            agent_version="2.0.0",
            current_versions={"configuration": "0"},
        )
        assert len(available) >= 1


# ─── Metrics Tests ────────────────────────────────────────────────────────


class TestConfigSyncMetrics:
    def test_initial(self):
        m = ConfigSyncMetricsCollector()
        snap = m.snapshot()
        assert snap.packages_created == 0

    def test_counters(self):
        m = ConfigSyncMetricsCollector()
        m.package_created()
        m.package_published()
        m.package_downloaded()
        m.package_failure()
        snap = m.snapshot()
        assert snap.packages_created == 1
        assert snap.packages_published == 1
        assert snap.packages_downloaded == 1
        assert snap.package_failures == 1


# ─── Repository Tests ─────────────────────────────────────────────────────


class TestConfigSyncRepository:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = ConfigSyncRepository(sqlite_session)
        self.session = sqlite_session

    async def test_create_and_get(self):
        pkg = ConfigurationPackage.create("configuration", "1", "data")
        await self.repo.create_package(pkg)
        got = await self.repo.get_package(pkg.package_id)
        assert got is not None
        assert got["package_type"] == "configuration"

    async def test_list_packages(self):
        for i in range(3):
            pkg = ConfigurationPackage.create("configuration", str(i))
            await self.repo.create_package(pkg)
        _records, total = await self.repo.list_packages()
        assert total >= 3

    async def test_update_state(self):
        pkg = ConfigurationPackage.create("configuration", "1")
        await self.repo.create_package(pkg)
        updated = await self.repo.update_state(pkg.package_id, PackageState.SIGNED)
        assert updated["state"] == "signed"

    async def test_available_packages(self):
        pkg = ConfigurationPackage.create("configuration", "1")
        await self.repo.create_package(pkg)
        await self.repo.update_state(pkg.package_id, PackageState.AVAILABLE)
        available = await self.repo.get_available_packages()
        assert len(available) >= 1

    async def test_machine_versions(self):
        await self.repo.set_machine_version("m-001", "configuration", "3")
        versions = await self.repo.get_machine_versions("m-001")
        assert len(versions) >= 1
        assert versions[0]["current_version"] == "3"


# ─── Service Tests ────────────────────────────────────────────────────────


class TestConfigSyncService:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = ConfigSyncRepository(sqlite_session)
        self.service = ConfigSyncService(repository=self.repo)

    async def test_create_package(self):
        from management_server.configsync.schemas import CreatePackageRequest

        req = CreatePackageRequest(package_type="configuration", version="2", payload="data")
        schema = await self.service.create_package(req)
        assert schema.package_id != ""
        assert schema.version == "2"

    async def test_publish_package(self):
        from management_server.configsync.schemas import CreatePackageRequest

        req = CreatePackageRequest(package_type="configuration", version="1", payload="data")
        schema = await self.service.create_package(req)
        published = await self.service.publish_package(schema.package_id)
        assert published.state == "available"

    async def test_get_package(self):
        from management_server.configsync.schemas import CreatePackageRequest

        req = CreatePackageRequest(package_type="configuration", version="1", payload="data")
        schema = await self.service.create_package(req)
        got = await self.service.get_package(schema.package_id)
        assert got is not None

    async def test_get_package_not_found(self):
        result = await self.service.get_package("nonexistent")
        assert result is None

    async def test_list_packages(self):
        from management_server.configsync.schemas import CreatePackageRequest

        req = CreatePackageRequest(package_type="configuration", version="1")
        await self.service.create_package(req)
        result = await self.service.list_packages()
        assert result["total"] >= 1

    async def test_get_metrics(self):
        metrics = await self.service.get_metrics()
        assert "packages_created" in metrics


# ─── API Tests ─────────────────────────────────────────────────────────────


class TestConfigSyncAPI:
    def test_list_packages_no_db(self, client: TestClient):
        resp = client.get("/api/v1/packages")
        assert resp.status_code in (503,)

    def test_create_package_no_db(self, client: TestClient):
        resp = client.post(
            "/api/v1/packages",
            json={"package_type": "configuration", "version": "1"},
        )
        assert resp.status_code in (503,)

    def test_get_package_no_db(self, client: TestClient):
        resp = client.get("/api/v1/packages/test-id")
        assert resp.status_code in (503,)
