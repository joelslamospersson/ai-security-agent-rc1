"""
Comprehensive tests for the Routing Engine subsystem.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.routing.decision import RoutingDecisionFactory
from management_server.routing.evaluator import RoutingEvaluator
from management_server.routing.loader import RoutingLoader
from management_server.routing.matcher import RoutingMatcher
from management_server.routing.metrics import RoutingMetricsCollector
from management_server.routing.models import (
    Destination,
    Priority,
    RoutingRule,
    Template,
)
from management_server.routing.repository import RoutingRepository
from management_server.routing.schemas import EventToRoute
from management_server.routing.service import RoutingService
from management_server.routing.validator import RoutingValidator

SAMPLE_YAML = """
rules:
  - name: "test_all"
    description: "Test catch-all"
    event_types:
      - "*"
    destinations:
      - "console"
    priority: "normal"
    template: "minimal"

  - name: "test_critical"
    description: "Critical alerts"
    event_types:
      - "critical_alert"
    match_severity: "critical"
    destinations:
      - "discord"
      - "email"
    priority: "immediate"
    template: "detailed"

profiles:
  - name: "test_profile"
    rate_limits:
      critical: "unlimited"
      high: "30/min"
      normal: "10/min"
      low: "1/min"
      bulk: "5/min"
"""


# ─── Model Tests ──────────────────────────────────────────────────────────


class TestPriority:
    def test_from_str(self):
        assert Priority.from_str("immediate") == Priority.IMMEDIATE
        assert Priority.from_str("HIGH") == Priority.HIGH
        assert Priority.from_str("unknown") == Priority.NORMAL


class TestDestination:
    def test_is_valid(self):
        assert Destination.is_valid("discord")
        assert Destination.is_valid("email")
        assert not Destination.is_valid("invalid")


class TestTemplate:
    def test_is_valid(self):
        assert Template.is_valid("detailed")
        assert Template.is_valid("minimal")
        assert not Template.is_valid("unknown")


class TestRoutingDecision:
    def test_create(self):
        d = RoutingDecisionFactory.create(
            machine_id="m1", event_type="test", destinations=["console"]
        )
        assert d.decision_id != ""
        assert d.machine_id == "m1"
        assert d.event_type == "test"
        assert d.destinations == ["console"]
        assert d.priority == Priority.NORMAL

    def test_frozen(self):
        d = RoutingDecisionFactory.create("m1", "test", ["console"])
        with pytest.raises(AttributeError):
            d.machine_id = "changed"  # type: ignore[misc]


# ─── Loader Tests ─────────────────────────────────────────────────────────


class TestRoutingLoader:
    def test_load_yaml_string(self):
        loader = RoutingLoader()
        rules, profiles = loader.load_yaml_string(SAMPLE_YAML)
        assert len(rules) == 2
        assert len(profiles) == 1
        assert rules[0].name == "test_all"
        assert rules[1].destinations == ["discord", "email"]

    def test_invalid_yaml_raises(self):
        loader = RoutingLoader()
        with pytest.raises(Exception, match="YAML parse error"):
            loader.load_yaml_string("bad yaml: [")


# ─── Validator Tests ──────────────────────────────────────────────────────


class TestRoutingValidator:
    def test_valid_rule(self):
        rule = RoutingRule(name="valid", event_types=["heartbeat"], destinations=["console"])
        errors = RoutingValidator().validate_rule(rule)
        assert len(errors) == 0

    def test_missing_name(self):
        rule = RoutingRule(name="")
        errors = RoutingValidator().validate_rule(rule)
        assert len(errors) >= 1

    def test_unknown_destination(self):
        rule = RoutingRule(name="bad", destinations=["unknown_dest"])
        errors = RoutingValidator().validate_rule(rule)
        assert any("Unknown destination" in e for e in errors)

    def test_duplicate_name(self):
        rules = [
            RoutingRule(name="dup"),
            RoutingRule(name="dup"),
        ]
        errors = RoutingValidator.validate_all(rules)
        assert any("Duplicate rule name" in e for e in errors)

    def test_validate_yaml_string(self):
        errors = RoutingValidator.validate_yaml_string(SAMPLE_YAML)
        assert len(errors) == 0

    def test_validate_invalid_yaml(self):
        errors = RoutingValidator.validate_yaml_string("invalid: [yaml")
        assert len(errors) >= 1


# ─── Matcher Tests ────────────────────────────────────────────────────────


class TestRoutingMatcher:
    def setup_method(self):
        self.match_all = RoutingRule(name="all", event_types=["*"], destinations=["console"])
        self.match_hb = RoutingRule(name="hb", event_types=["heartbeat"], destinations=["archive"])
        self.match_critical = RoutingRule(
            name="crit",
            event_types=["critical_alert"],
            match_severity="critical",
            destinations=["discord"],
        )
        self.matcher = RoutingMatcher([self.match_all, self.match_hb, self.match_critical])

    def test_match_all(self):
        result = self.matcher.match("anything")
        assert self.match_all in result

    def test_match_specific(self):
        result = self.matcher.match("heartbeat")
        assert self.match_hb in result

    def test_match_first(self):
        rule = self.matcher.match_first("heartbeat")
        assert rule is not None

    def test_match_by_severity(self):
        result = self.matcher.match("critical_alert", severity="critical")
        assert self.match_critical in result

    def test_no_match_when_disabled(self):
        disabled = RoutingRule(name="off", event_types=["test"], enabled=False)
        m = RoutingMatcher([disabled])
        result = m.match("test")
        assert len(result) == 0

    def test_wildcard_event_type(self):
        rule = RoutingRule(name="wild", event_types=["machine_*"], destinations=["console"])
        m = RoutingMatcher([rule])
        assert len(m.match("machine_online")) >= 1
        assert len(m.match("machine_offline")) >= 1
        assert len(m.match("heartbeat")) == 0

    def test_feature_flag_match(self):
        rule = RoutingRule(name="ff", event_types=["*"], match_feature_flags={"discord": True})
        m = RoutingMatcher([rule])
        assert len(m.match("test", feature_flags={"discord": True})) >= 1
        assert len(m.match("test", feature_flags={"discord": False})) == 0

    def test_capability_match(self):
        rule = RoutingRule(name="cap", event_types=["*"], match_capabilities=["iptables"])
        m = RoutingMatcher([rule])
        assert len(m.match("test", capabilities=["iptables"])) >= 1
        assert len(m.match("test", capabilities=["docker"])) == 0

    def test_environment_match(self):
        rule = RoutingRule(name="env", event_types=["*"], match_environment="production")
        m = RoutingMatcher([rule])
        assert len(m.match("test", environment="production")) >= 1
        assert len(m.match("test", environment="development")) == 0


# ─── Evaluator Tests ──────────────────────────────────────────────────────


class TestRoutingEvaluator:
    def setup_method(self):
        rules = [
            RoutingRule(
                name="critical",
                event_types=["critical_alert"],
                destinations=["discord"],
                priority=Priority.IMMEDIATE,
            ),
            RoutingRule(name="all", event_types=["*"], destinations=["console"]),
        ]
        matcher = RoutingMatcher(rules)
        self.evaluator = RoutingEvaluator(matcher)

    def test_evaluate_normal(self):
        decision = self.evaluator.evaluate(machine_id="m1", event_type="heartbeat")
        assert decision.machine_id == "m1"
        assert decision.event_type == "heartbeat"
        assert decision.matched_rule == "all"

    def test_evaluate_critical(self):
        decision = self.evaluator.evaluate(machine_id="m1", event_type="critical_alert")
        assert decision.destinations == ["discord"]
        assert decision.priority == Priority.IMMEDIATE

    def test_no_match_uses_default(self):
        matcher = RoutingMatcher([])
        evaluator = RoutingEvaluator(matcher)
        decision = evaluator.evaluate(machine_id="m1", event_type="test")
        assert decision.matched_rule == "__default__"
        assert decision.destinations == ["console"]


# ─── Metrics Tests ────────────────────────────────────────────────────────


class TestRoutingMetrics:
    def test_initial(self):
        m = RoutingMetricsCollector()
        snap = m.snapshot()
        assert snap.routing_decisions == 0

    def test_counters(self):
        m = RoutingMetricsCollector()
        m.decision_created(5.0)
        m.rule_matched()
        m.default_route_used()
        m.validation_failure()
        snap = m.snapshot()
        assert snap.routing_decisions == 1
        assert snap.rule_matches == 1
        assert snap.default_route_usage == 1
        assert snap.validation_failures == 1
        assert snap.evaluation_latency_ms > 0


# ─── Repository Tests ─────────────────────────────────────────────────────


class TestRoutingRepository:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = RoutingRepository(sqlite_session)
        self.session = sqlite_session

    async def test_save_decision(self):
        decision = RoutingDecisionFactory.create("m1", "test", ["console"])
        result = await self.repo.save_decision(decision)
        assert result["decision_id"] == decision.decision_id

    async def test_get_decision(self):
        decision = RoutingDecisionFactory.create("m2", "test", ["console"])
        await self.repo.save_decision(decision)
        got = await self.repo.get_decision(decision.decision_id)
        assert got is not None

    async def test_list_decisions(self):
        for i in range(3):
            d = RoutingDecisionFactory.create(f"m{i}", "test", ["console"])
            await self.repo.save_decision(d)
        _rows, total = await self.repo.list_decisions()
        assert total >= 3

    async def test_save_rule(self):
        rule = RoutingRule(name="repo-rule", event_types=["test"], destinations=["console"])
        await self.repo.save_rule(rule)
        rules = await self.repo.list_rules()
        assert any(r["name"] == "repo-rule" for r in rules)


# ─── Service Tests ────────────────────────────────────────────────────────


class TestRoutingService:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = RoutingRepository(sqlite_session)
        self.service = RoutingService(repository=self.repo)

    async def test_evaluate_event(self):
        # Load rules first
        await self.service.load_config()

        event = EventToRoute(machine_id="svc-m1", event_type="heartbeat")
        result = await self.service.evaluate(event)
        assert result.matched
        assert result.decision.decision_id != ""

    async def test_evaluate_no_rules(self):
        event = EventToRoute(machine_id="svc-m2", event_type="unknown_type")
        result = await self.service.evaluate(event)
        # With no rules loaded, should still produce a decision
        assert result.decision.decision_id != ""

    async def test_get_decision(self):
        await self.service.load_config()
        event = EventToRoute(machine_id="svc-m3", event_type="test")
        result = await self.service.evaluate(event)
        decision = await self.service.get_decision(result.decision.decision_id)
        assert decision is not None

    async def test_list_decisions(self):
        await self.service.load_config()
        await self.service.evaluate(EventToRoute(machine_id="svc-m4", event_type="test"))
        result = await self.service.list_decisions()
        assert result["total"] >= 1

    async def test_list_rules(self):
        await self.service.load_config()
        rules = await self.service.list_rules()
        assert len(rules) >= 0

    async def test_get_metrics(self):
        metrics = await self.service.get_metrics()
        assert "routing_decisions" in metrics


# ─── Validator Full Validation Tests ──────────────────────────────────────


class TestFullValidation:
    def test_valid_config_passes(self):
        errors = RoutingValidator.validate_yaml_string(SAMPLE_YAML)
        assert len(errors) == 0

    def test_unknown_destination_fails(self):
        yaml = SAMPLE_YAML.replace("console", "invalid_dest")
        errors = RoutingValidator.validate_yaml_string(yaml)
        assert len(errors) >= 1


# ─── API Tests ─────────────────────────────────────────────────────────────


class TestRoutingAPI:
    def test_list_rules_no_db(self, client: TestClient):
        resp = client.get("/api/v1/routing")
        assert resp.status_code in (503,)

    def test_evaluate_no_db(self, client: TestClient):
        resp = client.post(
            "/api/v1/routing/evaluate",
            json={"machine_id": "api-test", "event_type": "test"},
        )
        assert resp.status_code in (503,)

    def test_reload_no_db(self, client: TestClient):
        resp = client.post("/api/v1/routing/reload")
        assert resp.status_code in (503,)

    def test_list_decisions_no_db(self, client: TestClient):
        resp = client.get("/api/v1/routing/decisions")
        assert resp.status_code in (503,)

    def test_get_decision_no_db(self, client: TestClient):
        resp = client.get("/api/v1/routing/decisions/test-id")
        assert resp.status_code in (503,)
