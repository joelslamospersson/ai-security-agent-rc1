"""
Comprehensive tests for the Rule Engine.
"""

from __future__ import annotations

import time

import pytest

from security_agent.rules import (
    Condition,
    LogicalOp,
    Rule,
    RuleEngine,
    RuleMatch,
)
from security_agent.rules.compiler import compile_rule, compile_rules
from security_agent.rules.context import RuleContext
from security_agent.rules.exceptions import (
    RuleCompilationError,
    RuleLoadError,
)
from security_agent.rules.loader import _dict_to_condition, _dict_to_rule, load_rules
from security_agent.rules.matcher import evaluate_condition
from security_agent.rules.models import ConditionOp
from security_agent.rules.validator import validate_rules

# =========================================================================
# Condition Matching Tests
# =========================================================================


class TestConditionMatching:
    def test_equals_match(self) -> None:
        c = Condition(field="severity", operator=ConditionOp.EQUALS, value=7)
        assert evaluate_condition(c, {"severity": 7})

    def test_equals_no_match(self) -> None:
        c = Condition(field="severity", operator=ConditionOp.EQUALS, value=7)
        assert not evaluate_condition(c, {"severity": 3})

    def test_not_equals(self) -> None:
        c = Condition(field="source", operator=ConditionOp.NOT_EQUALS, value="ssh")
        assert evaluate_condition(c, {"source": "nginx"})
        assert not evaluate_condition(c, {"source": "ssh"})

    def test_contains(self) -> None:
        c = Condition(field="message", operator=ConditionOp.CONTAINS, value="failed")
        assert evaluate_condition(c, {"message": "Failed password"})
        assert not evaluate_condition(c, {"message": "Accepted password"})

    def test_regex(self) -> None:
        c = Condition(
            field="message",
            operator=ConditionOp.REGEX,
            value=r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
        )
        compiled = {
            "message": __import__("re").compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
        }
        assert evaluate_condition(c, {"message": "from 1.2.3.4 port 22"}, compiled)

    def test_starts_with(self) -> None:
        c = Condition(field="message", operator=ConditionOp.STARTS_WITH, value="Failed")
        assert evaluate_condition(c, {"message": "Failed password"})
        assert not evaluate_condition(c, {"message": "Accepted password"})

    def test_ends_with(self) -> None:
        c = Condition(field="source", operator=ConditionOp.ENDS_WITH, value=".service")
        assert evaluate_condition(c, {"source": "sshd.service"})
        assert not evaluate_condition(c, {"source": "sshd"})

    def test_exists(self) -> None:
        c = Condition(field="source_ip", operator=ConditionOp.EXISTS)
        assert evaluate_condition(c, {"source_ip": "1.2.3.4"})
        assert not evaluate_condition(c, {})

    def test_missing(self) -> None:
        c = Condition(field="source_ip", operator=ConditionOp.MISSING)
        assert evaluate_condition(c, {})
        assert not evaluate_condition(c, {"source_ip": "1.2.3.4"})

    def test_gt(self) -> None:
        c = Condition(field="severity", operator=ConditionOp.GT, value=5)
        assert evaluate_condition(c, {"severity": 7})
        assert not evaluate_condition(c, {"severity": 3})

    def test_gte(self) -> None:
        c = Condition(field="severity", operator=ConditionOp.GTE, value=5)
        assert evaluate_condition(c, {"severity": 5})
        assert not evaluate_condition(c, {"severity": 4})

    def test_lt(self) -> None:
        c = Condition(field="severity", operator=ConditionOp.LT, value=5)
        assert evaluate_condition(c, {"severity": 3})
        assert not evaluate_condition(c, {"severity": 7})

    def test_lte(self) -> None:
        c = Condition(field="severity", operator=ConditionOp.LTE, value=5)
        assert evaluate_condition(c, {"severity": 5})
        assert not evaluate_condition(c, {"severity": 7})

    def test_and_operator(self) -> None:
        c = Condition(
            logical=LogicalOp.AND,
            conditions=(
                Condition(field="severity", operator=ConditionOp.GTE, value=5),
                Condition(field="source", operator=ConditionOp.EQUALS, value="ssh"),
            ),
        )
        assert evaluate_condition(c, {"severity": 7, "source": "ssh"})
        assert not evaluate_condition(c, {"severity": 7, "source": "nginx"})
        assert not evaluate_condition(c, {"severity": 3, "source": "ssh"})

    def test_or_operator(self) -> None:
        c = Condition(
            logical=LogicalOp.OR,
            conditions=(
                Condition(field="severity", operator=ConditionOp.GTE, value=9),
                Condition(field="source", operator=ConditionOp.EQUALS, value="kernel"),
            ),
        )
        assert evaluate_condition(c, {"severity": 10})
        assert evaluate_condition(c, {"source": "kernel"})
        assert not evaluate_condition(c, {"severity": 3, "source": "ssh"})

    def test_not_operator(self) -> None:
        c = Condition(
            logical=LogicalOp.NOT,
            conditions=(
                Condition(field="source", operator=ConditionOp.EQUALS, value="kernel"),
            ),
        )
        assert evaluate_condition(c, {"source": "ssh"})
        assert not evaluate_condition(c, {"source": "kernel"})

    def test_nested_logical(self) -> None:
        """Test nested AND/OR combination."""
        c = Condition(
            logical=LogicalOp.AND,
            conditions=(
                Condition(field="severity", operator=ConditionOp.GTE, value=5),
                Condition(
                    logical=LogicalOp.OR,
                    conditions=(
                        Condition(
                            field="source", operator=ConditionOp.EQUALS, value="ssh"
                        ),
                        Condition(
                            field="source", operator=ConditionOp.EQUALS, value="sudo"
                        ),
                    ),
                ),
            ),
        )
        assert evaluate_condition(c, {"severity": 7, "source": "ssh"})
        assert evaluate_condition(c, {"severity": 7, "source": "sudo"})
        assert not evaluate_condition(c, {"severity": 7, "source": "nginx"})
        assert not evaluate_condition(c, {"severity": 3, "source": "ssh"})

    def test_missing_field(self) -> None:
        c = Condition(field="nonexistent", operator=ConditionOp.EQUALS, value="x")
        assert not evaluate_condition(c, {"severity": 5})


# =========================================================================
# Rule Tests
# =========================================================================


class TestRule:
    def test_rule_creation(self) -> None:
        r = Rule(
            id="test-001", name="Test Rule", severity=5, confidence=80, threat_score=50
        )
        assert r.id == "test-001"
        assert r.name == "Test Rule"
        assert r.severity == 5

    def test_rule_frozen(self) -> None:
        r = Rule(id="t", name="t")
        with pytest.raises(AttributeError):
            r.id = "x"  # type: ignore[misc]

    def test_invalid_severity(self) -> None:
        with pytest.raises(ValueError):
            Rule(id="t", name="t", severity=15)

    def test_invalid_confidence(self) -> None:
        with pytest.raises(ValueError):
            Rule(id="t", name="t", confidence=150)

    def test_invalid_threat_score(self) -> None:
        with pytest.raises(ValueError):
            Rule(id="t", name="t", threat_score=200)


class TestRuleMatch:
    def test_creation(self) -> None:
        m = RuleMatch(
            rule_id="r1", rule_name="test", confidence=80, severity=5, threat_score=50
        )
        assert m.rule_id == "r1"
        assert m.confidence == 80

    def test_frozen(self) -> None:
        m = RuleMatch()
        with pytest.raises(AttributeError):
            m.rule_id = "x"  # type: ignore[misc]

    def test_invalid_confidence(self) -> None:
        with pytest.raises(ValueError):
            RuleMatch(confidence=150)

    def test_invalid_severity(self) -> None:
        with pytest.raises(ValueError):
            RuleMatch(severity=15)


# =========================================================================
# Compiler Tests
# =========================================================================


class TestCompiler:
    def test_compile_regex(self) -> None:
        rule = Rule(
            id="r1",
            name="r1",
            severity=5,
            confidence=80,
            threat_score=50,
            conditions=Condition(
                field="message", operator=ConditionOp.REGEX, value=r"fail(ed)?"
            ),
        )
        compiled = compile_rule(rule)
        assert "patterns" in compiled
        assert "message" in compiled["patterns"]

    def test_compile_invalid_regex_raises(self) -> None:
        rule = Rule(
            id="r1",
            name="r1",
            severity=5,
            confidence=80,
            threat_score=50,
            conditions=Condition(
                field="message", operator=ConditionOp.REGEX, value=r"[invalid"
            ),
        )
        with pytest.raises(RuleCompilationError):
            compile_rule(rule)

    def test_compile_multiple_rules(self) -> None:
        rules = [
            Rule(
                id="r1",
                name="r1",
                severity=5,
                confidence=80,
                threat_score=50,
                conditions=Condition(field="x", operator=ConditionOp.REGEX, value=r"a"),
            ),
            Rule(
                id="r2",
                name="r2",
                severity=5,
                confidence=80,
                threat_score=50,
                conditions=Condition(field="y", operator=ConditionOp.REGEX, value=r"b"),
            ),
        ]
        compiled = compile_rules(rules)
        assert "r1" in compiled
        assert "r2" in compiled


# =========================================================================
# Validator Tests
# =========================================================================


class TestValidator:
    def test_valid_rules_pass(self) -> None:
        rules = [
            {
                "id": "r1",
                "name": "test",
                "severity": 5,
                "confidence": 80,
                "threat_score": 50,
                "conditions": {"field": "severity", "operator": "gte", "value": 5},
            },
        ]
        errors = validate_rules(rules)
        assert errors == []

    def test_duplicate_id_fails(self) -> None:
        rules = [
            {
                "id": "r1",
                "name": "a",
                "conditions": {"field": "x", "operator": "equals", "value": 1},
            },
            {
                "id": "r1",
                "name": "b",
                "conditions": {"field": "x", "operator": "equals", "value": 2},
            },
        ]
        errors = validate_rules(rules)
        assert any("Duplicate" in e for e in errors)

    def test_missing_name_fails(self) -> None:
        rules = [
            {"id": "r1", "conditions": {"field": "x", "operator": "equals", "value": 1}}
        ]
        errors = validate_rules(rules)
        assert any("name" in e for e in errors)

    def test_invalid_operator_fails(self) -> None:
        rules = [
            {
                "id": "r1",
                "name": "t",
                "conditions": {"field": "x", "operator": "invalid_op", "value": 1},
            }
        ]
        errors = validate_rules(rules)
        assert any("operator" in e for e in errors)

    def test_out_of_range_severity_fails(self) -> None:
        rules = [
            {
                "id": "r1",
                "name": "t",
                "severity": 15,
                "confidence": 80,
                "threat_score": 50,
                "conditions": {"field": "x", "operator": "equals", "value": 1},
            }
        ]
        errors = validate_rules(rules)
        assert any("severity" in e for e in errors)

    def test_invalid_logical_operator_fails(self) -> None:
        rules = [
            {
                "id": "r1",
                "name": "t",
                "conditions": {"logical": "xor", "conditions": []},
            }
        ]
        errors = validate_rules(rules)
        assert any("logical" in e for e in errors)


# =========================================================================
# Loader Tests
# =========================================================================


class TestLoader:
    def test_dict_to_condition_leaf(self) -> None:
        c = _dict_to_condition({"field": "severity", "operator": "gte", "value": 5})
        assert c.field == "severity"
        assert c.operator == ConditionOp.GTE

    def test_dict_to_condition_logical(self) -> None:
        c = _dict_to_condition(
            {
                "logical": "and",
                "conditions": [
                    {"field": "a", "operator": "equals", "value": 1},
                    {"field": "b", "operator": "equals", "value": 2},
                ],
            }
        )
        assert c.logical == LogicalOp.AND
        assert len(c.conditions) == 2

    def test_dict_to_rule(self) -> None:
        r = _dict_to_rule(
            {
                "id": "test-001",
                "name": "Test",
                "severity": 5,
                "confidence": 80,
                "threat_score": 50,
                "conditions": {"field": "severity", "operator": "gte", "value": 5},
            }
        )
        assert r.id == "test-001"
        assert r.severity == 5

    def test_load_core_yaml(self) -> None:
        rules = load_rules("rules/core.yaml")
        assert len(rules) >= 5
        assert any(r.id == "core-001" for r in rules)

    def test_load_nonexistent_raises(self) -> None:
        with pytest.raises(RuleLoadError):
            load_rules("rules/nonexistent.yaml")


# =========================================================================
# Rule Engine Tests
# =========================================================================


class TestRuleEngine:
    def test_load_rules(self) -> None:
        engine = RuleEngine()
        rules = [
            Rule(
                id="r1",
                name="test",
                severity=5,
                confidence=80,
                threat_score=50,
                conditions=Condition(
                    field="severity", operator=ConditionOp.GTE, value=5
                ),
            ),
        ]
        engine.load_rules(rules)
        assert engine.rule_count == 1
        assert engine.enabled_count == 1

    def test_evaluate_match(self) -> None:
        engine = RuleEngine()
        rules = [
            Rule(
                id="r1",
                name="high_severity",
                severity=5,
                confidence=80,
                threat_score=50,
                conditions=Condition(
                    field="severity", operator=ConditionOp.GTE, value=5
                ),
            ),
        ]
        engine.load_rules(rules)
        matches = engine.evaluate({"severity": 7})
        assert len(matches) == 1
        assert matches[0].rule_id == "r1"

    def test_evaluate_no_match(self) -> None:
        engine = RuleEngine()
        rules = [
            Rule(
                id="r1",
                name="high_severity",
                severity=5,
                confidence=80,
                threat_score=50,
                conditions=Condition(
                    field="severity", operator=ConditionOp.GTE, value=5
                ),
            ),
        ]
        engine.load_rules(rules)
        matches = engine.evaluate({"severity": 3})
        assert len(matches) == 0

    def test_disabled_rule_skipped(self) -> None:
        engine = RuleEngine()
        rules = [
            Rule(
                id="r1",
                name="r1",
                enabled=False,
                severity=5,
                confidence=80,
                threat_score=50,
                conditions=Condition(
                    field="severity", operator=ConditionOp.GTE, value=0
                ),
            ),
        ]
        engine.load_rules(rules)
        matches = engine.evaluate({"severity": 5})
        assert len(matches) == 0

    def test_enable_disable(self) -> None:
        engine = RuleEngine()
        rules = [
            Rule(
                id="r1",
                name="r1",
                enabled=True,
                severity=5,
                confidence=80,
                threat_score=50,
                conditions=Condition(
                    field="severity", operator=ConditionOp.GTE, value=0
                ),
            ),
        ]
        engine.load_rules(rules)
        assert engine.enabled_count == 1
        engine.disable_rule("r1")
        assert engine.enabled_count == 0
        engine.enable_rule("r1")
        assert engine.enabled_count == 1

    def test_evaluate_core_yaml(self) -> None:
        from security_agent.rules.loader import load_rules

        rules = load_rules("rules/core.yaml")
        engine = RuleEngine()
        engine.load_rules(rules)
        matches = engine.evaluate({"severity": 10, "source": "sshd"})
        assert len(matches) >= 1
        assert any(m.rule_id == "core-001" for m in matches)  # severity >= 7
        assert any(m.rule_id == "core-003" for m in matches)  # severity >= 9

    def test_evaluate_with_context(self) -> None:
        engine = RuleEngine()
        rules = [
            Rule(
                id="r1",
                name="r1",
                severity=5,
                confidence=80,
                threat_score=50,
                conditions=Condition(
                    field="severity", operator=ConditionOp.GTE, value=0
                ),
            )
        ]
        engine.load_rules(rules)
        ctx = RuleContext(correlation_id="test-123")
        matches = engine.evaluate({"severity": 5}, ctx)
        assert matches[0].correlation_id == "test-123"

    def test_metrics(self) -> None:
        engine = RuleEngine()
        rules = [
            Rule(
                id="r1",
                name="r1",
                severity=5,
                confidence=80,
                threat_score=50,
                conditions=Condition(field="x", operator=ConditionOp.EQUALS, value=1),
            )
        ]
        engine.load_rules(rules)
        engine.evaluate({"x": 1})
        engine.evaluate({"x": 2})
        snap = engine.metrics_snapshot()
        assert snap.rules_loaded >= 1
        assert snap.rules_evaluated >= 2


# =========================================================================
# Benchmarks
# =========================================================================


class TestBenchmarks:
    @pytest.mark.benchmark
    def test_100_rules(self) -> None:
        engine = RuleEngine()
        rules = [
            Rule(
                id=f"r{i}",
                name=f"r{i}",
                severity=5,
                confidence=80,
                threat_score=50,
                conditions=Condition(
                    field="severity", operator=ConditionOp.GTE, value=3
                ),
            )
            for i in range(100)
        ]
        engine.load_rules(rules)
        count = 1000
        t = time.monotonic()
        for _ in range(count):
            engine.evaluate({"severity": 7})
        elapsed = time.monotonic() - t
        ev_per_s = count / elapsed
        print(f"\n  100 rules: {ev_per_s:.0f} ev/s ({count} in {elapsed:.3f}s)")
        assert ev_per_s > 10

    @pytest.mark.benchmark
    def test_1000_rules(self) -> None:
        engine = RuleEngine()
        rules = [
            Rule(
                id=f"r{i}",
                name=f"r{i}",
                severity=5,
                confidence=80,
                threat_score=50,
                conditions=Condition(
                    field="severity", operator=ConditionOp.GTE, value=3
                ),
            )
            for i in range(1000)
        ]
        engine.load_rules(rules)
        count = 200
        t = time.monotonic()
        for _ in range(count):
            engine.evaluate({"severity": 7})
        elapsed = time.monotonic() - t
        ev_per_s = count / elapsed
        print(f"\n  1000 rules: {ev_per_s:.0f} ev/s ({count} in {elapsed:.3f}s)")
        assert ev_per_s > 10

    @pytest.mark.benchmark
    def test_core_rules_throughput(self) -> None:
        from security_agent.rules.loader import load_rules

        rules = load_rules("rules/core.yaml")
        engine = RuleEngine()
        engine.load_rules(rules)
        count = 5000
        t = time.monotonic()
        for _ in range(count):
            engine.evaluate(
                {"severity": 7, "source": "sshd", "message": "Failed password"}
            )
        elapsed = time.monotonic() - t
        ev_per_s = count / elapsed
        print(f"\n  Core rules: {ev_per_s:.0f} ev/s ({count} in {elapsed:.3f}s)")
