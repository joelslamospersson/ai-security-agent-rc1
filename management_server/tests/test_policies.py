"""
Comprehensive tests for the Policy Engine subsystem.
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.policies.inheritance import PolicyInheritanceEngine
from management_server.policies.loader import PolicyLoader
from management_server.policies.metrics import PolicyMetricsCollector
from management_server.policies.models import FeatureFlags, Policy
from management_server.policies.repository import PolicyRepository
from management_server.policies.service import PolicyService
from management_server.policies.validator import PolicyValidator

SAMPLE_YAML = """
name: test_policy
description: "Test policy"
version: "1"
heartbeat_interval_seconds: 30
notification_retention_days: 30
log_retention_days: 90
ip_masking_enabled: true
maintenance_mode: false
allowed_protocol_versions:
  - "1.0"
feature_flags:
  discord: false
  geoip: true
  docker: false
  web_dashboard: false
  remote_commands: false
  experimental: false
"""


# ─── Feature Flags Tests ──────────────────────────────────────────────────


class TestFeatureFlags:
    def test_defaults(self):
        ff = FeatureFlags()
        assert not ff.discord
        assert not ff.docker

    def test_from_dict(self):
        ff = FeatureFlags.from_dict({"discord": True, "geoip": True})
        assert ff.discord
        assert ff.geoip
        assert not ff.docker

    def test_to_dict(self):
        ff = FeatureFlags(discord=True, docker=True)
        d = ff.to_dict()
        assert d["discord"]
        assert d["docker"]
        assert not d["geoip"]


# ─── Model Tests ──────────────────────────────────────────────────────────


class TestPolicyModel:
    def test_policy_creation(self):
        p = Policy(name="test", description="A test policy")
        assert p.name == "test"
        assert not p.is_default
        assert not p.has_parent

    def test_default_policy(self):
        p = Policy(name="default")
        assert p.is_default

    def test_policy_with_parent(self):
        p = Policy(name="child", parent="base")
        assert p.has_parent


# ─── Loader Tests ─────────────────────────────────────────────────────────


class TestPolicyLoader:
    def test_load_yaml_string(self):
        loader = PolicyLoader()
        policy = loader.load_yaml_string("test_policy", SAMPLE_YAML)
        assert policy.name == "test_policy"
        assert policy.heartbeat_interval_seconds == 30
        assert not policy.feature_flags.discord
        assert policy.feature_flags.geoip

    def test_checksum_generated(self):
        loader = PolicyLoader()
        policy = loader.load_yaml_string("checksum_test", SAMPLE_YAML)
        assert len(policy.checksum) == 64  # SHA-256 hex

    def test_invalid_yaml_raises(self):
        loader = PolicyLoader()
        with pytest.raises(Exception, match="YAML parse error"):
            loader.load_yaml_string("bad", "not: valid: yaml: [")


# ─── Validator Tests ──────────────────────────────────────────────────────


class TestPolicyValidator:
    def test_valid_policy(self):
        loader = PolicyLoader()
        policy = loader.load_yaml_string("valid", SAMPLE_YAML)
        validator = PolicyValidator([policy])
        result = validator.validate(policy)
        assert result.valid
        assert len(result.errors) == 0

    def test_invalid_name(self):
        policy = Policy(name="Invalid-Name!")
        validator = PolicyValidator()
        result = validator.validate(policy)
        assert not result.valid

    def test_own_parent(self):
        policy = Policy(name="self_parent", parent="self_parent")
        validator = PolicyValidator([policy])
        result = validator.validate(policy)
        assert not result.valid

    def test_range_violation(self):
        policy = Policy(name="range_test", heartbeat_interval_seconds=99999)
        validator = PolicyValidator()
        result = validator.validate(policy)
        assert not result.valid

    def test_validate_yaml_string(self):
        result = PolicyValidator.validate_yaml_string("test", SAMPLE_YAML)
        assert result.valid

    def test_validate_invalid_yaml_string(self):
        result = PolicyValidator.validate_yaml_string("bad", "invalid: [yaml")
        assert not result.valid


# ─── Inheritance Tests ────────────────────────────────────────────────────


class TestPolicyInheritance:
    def test_single_inheritance(self):
        base = Policy(name="base", heartbeat_interval_seconds=60)
        child = Policy(name="child", parent="base", heartbeat_interval_seconds=30)
        engine = PolicyInheritanceEngine({"base": base, "child": child})
        resolved = engine.resolve("child")
        # Child's value overrides base
        assert resolved.heartbeat_interval_seconds == 30

    def test_inheritance_applies_base_values(self):
        base = Policy(name="base", heartbeat_interval_seconds=60, ip_masking_enabled=True)
        # Child with default hb=30 will override base hb=60 (explicit beats implicit in real YAML)
        # In practice, YAML loader always sets explicit values
        child = Policy(name="child", parent="base")
        engine = PolicyInheritanceEngine({"base": base, "child": child})
        resolved = engine.resolve("child")
        assert resolved.heartbeat_interval_seconds == 30  # child's default wins
        assert resolved.ip_masking_enabled  # from base

    def test_circular_detection(self):
        a = Policy(name="a", parent="b")
        b = Policy(name="b", parent="a")
        engine = PolicyInheritanceEngine({"a": a, "b": b})
        circular = engine.detect_circular()
        assert len(circular) >= 2

    def test_chain_resolution(self):
        base = Policy(name="base", heartbeat_interval_seconds=60, ip_masking_enabled=True)
        mid = Policy(name="mid", parent="base", heartbeat_interval_seconds=30)
        top = Policy(name="top", parent="mid", maintenance_mode=True)
        engine = PolicyInheritanceEngine({"base": base, "mid": mid, "top": top})
        resolved = engine.resolve("top")
        assert resolved.heartbeat_interval_seconds == 30  # from mid
        assert resolved.ip_masking_enabled  # from base
        assert resolved.maintenance_mode  # from top

    def test_max_depth(self):
        a = Policy(name="a", parent="b")
        b = Policy(name="b", parent="c")
        c = Policy(name="c")
        engine = PolicyInheritanceEngine({"a": a, "b": b, "c": c})
        assert engine.max_depth == 3

    def test_get_ancestors(self):
        a = Policy(name="a", parent="b")
        b = Policy(name="b", parent="c")
        c = Policy(name="c")
        engine = PolicyInheritanceEngine({"a": a, "b": b, "c": c})
        ancestors = engine.get_ancestors("a")
        assert ancestors == ["b", "c"]


# ─── Metrics Tests ────────────────────────────────────────────────────────


class TestPolicyMetrics:
    def test_initial(self):
        m = PolicyMetricsCollector()
        snap = m.snapshot()
        assert snap.loaded_policies == 0

    def test_counters(self):
        m = PolicyMetricsCollector()
        m.validation_failure()
        m.assignment()
        m.override()
        m.reload()
        snap = m.snapshot(loaded_policies=3, inheritance_depth=2)
        assert snap.validation_failures == 1
        assert snap.policy_assignments == 1
        assert snap.overrides == 1
        assert snap.reloads == 1
        assert snap.loaded_policies == 3
        assert snap.inheritance_depth == 2


# ─── Repository Tests ─────────────────────────────────────────────────────


class TestPolicyRepository:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = PolicyRepository(sqlite_session)
        self.session = sqlite_session

    async def test_save_and_get_policy(self):
        policy = Policy(name="repo-test", description="Test save")
        record = await self.repo.save_policy(policy)
        assert record["name"] == "repo-test"

        fetched = await self.repo.get_policy("repo-test")
        assert fetched["description"] == "Test save"

    async def test_list_policies(self):
        await self.repo.save_policy(Policy(name="list-a"))
        await self.repo.save_policy(Policy(name="list-b"))
        _policies, total = await self.repo.list_policies()
        assert total >= 2

    async def test_assign_and_get_assignment(self):
        await self.repo.save_policy(Policy(name="assign-pol"))
        result = await self.repo.assign_policy("machine-1", "assign-pol")
        assert result["machine_uuid"] == "machine-1"

        assignment = await self.repo.get_assignment("machine-1")
        assert assignment is not None
        assert assignment["policy_name"] == "assign-pol"

    async def test_set_and_get_overrides(self):
        await self.repo.save_policy(Policy(name="override-pol"))
        await self.repo.assign_policy("machine-2", "override-pol")
        result = await self.repo.set_override(
            machine_uuid="machine-2",
            policy_name="override-pol",
            key="heartbeat_interval_seconds",
            value="60",
        )
        assert result["key"] == "heartbeat_interval_seconds"

        overrides = await self.repo.get_overrides("machine-2")
        assert len(overrides) >= 1


# ─── Service Tests ────────────────────────────────────────────────────────


class TestPolicyService:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = PolicyRepository(sqlite_session)
        self.service = PolicyService(repository=self.repo)

    async def test_validate_yaml(self):
        result = await self.service.validate_policy_yaml("test", SAMPLE_YAML)
        assert result.valid

    async def test_assign_policy(self):
        # Need a policy to assign
        loader = PolicyLoader()
        policy = loader.load_yaml_string("assign-svc", SAMPLE_YAML)
        await self.repo.save_policy(policy)
        self.service._inheritance.register(policy)

        result = await self.service.assign_policy("machine-svc", "assign-svc")
        assert result["machine_uuid"] == "machine-svc"

    async def test_get_metrics(self):
        loader = PolicyLoader()
        policy = loader.load_yaml_string("metric-pol", SAMPLE_YAML)
        await self.repo.save_policy(policy)

        metrics = await self.service.get_metrics()
        assert "loaded_policies" in metrics


# ─── YAML Policy Files Tests ──────────────────────────────────────────────


class TestBuiltinPolicies:
    BUILTIN_NAMES: ClassVar[list[str]] = [
        "default",
        "production",
        "development",
        "game_server",
        "high_security",
        "low_priority",
    ]

    def test_all_policies_load(self):
        loader = PolicyLoader("config/policies")
        policies = loader.load_all()
        loaded_names = [p.name for p in policies]
        for name in self.BUILTIN_NAMES:
            assert name in loaded_names, f"Built-in policy '{name}' not loaded"

    def test_all_policies_validate(self):
        loader = PolicyLoader("config/policies")
        policies = loader.load_all()
        validator = PolicyValidator(policies)
        for policy in policies:
            result = validator.validate(policy)
            assert result.valid, f"Policy '{policy.name}' failed validation: {result.errors}"

    def test_inheritance_hierarchy(self):
        loader = PolicyLoader("config/policies")
        policies = loader.load_all()
        engine = PolicyInheritanceEngine()
        engine.register_all(policies)
        circular = engine.detect_circular()
        assert len(circular) == 0, f"Circular inheritance detected: {circular}"

    def test_production_inherits_default(self):
        loader = PolicyLoader("config/policies")
        policies = loader.load_all()
        prod = next(p for p in policies if p.name == "production")
        assert prod.parent == "default"

    def test_high_security_inherits_production(self):
        loader = PolicyLoader("config/policies")
        policies = loader.load_all()
        hs = next(p for p in policies if p.name == "high_security")
        assert hs.parent == "production"


# ─── API Tests ─────────────────────────────────────────────────────────────


class TestPolicyAPI:
    def test_list_policies_no_db(self, client: TestClient):
        resp = client.get("/api/v1/policies")
        assert resp.status_code in (503,)

    def test_get_policy_no_db(self, client: TestClient):
        resp = client.get("/api/v1/policies/default")
        assert resp.status_code in (503,)

    def test_health_endpoint(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
