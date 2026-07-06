"""
Comprehensive tests for the Threat Engine.
"""

from __future__ import annotations

import time

import pytest

from security_agent.correlation.models import IncidentState, SecurityIncident
from security_agent.threat import (
    RecommendedAction,
    RiskLevel,
    ThreatAssessment,
    ThreatEngine,
)
from security_agent.threat.actions import action_name, action_requires_attention
from security_agent.threat.scorer import (
    calculate_confidence,
    calculate_severity,
    calculate_threat_score,
    classify_risk,
    recommend_action,
)


def make_incident(
    state=IncidentState.COMPLETED,
    confidence_modifier=30,
    progress=100,
    matched_rules=("r1", "r2", "r3"),
    matched_events=("e1", "e2", "e3"),
):
    return SecurityIncident(
        incident_id="inc-001",
        attack_chain_id="chain-001",
        correlation_id="corr-001",
        state=state,
        matched_rules=matched_rules,
        matched_events=matched_events,
        progress=progress,
        confidence_modifier=confidence_modifier,
    )


class TestThreatAssessment:
    def test_creation(self):
        t = ThreatAssessment(
            incident_id="i1", confidence=80, threat_score=65, severity=7
        )
        assert t.incident_id == "i1"
        assert t.confidence == 80
        assert t.threat_score == 65

    def test_frozen(self):
        t = ThreatAssessment()
        with pytest.raises(AttributeError):
            t.confidence = 50  # type: ignore[misc]

    def test_invalid_confidence(self):
        with pytest.raises(ValueError):
            ThreatAssessment(confidence=150)

    def test_invalid_threat_score(self):
        with pytest.raises(ValueError):
            ThreatAssessment(threat_score=150)

    def test_invalid_severity(self):
        with pytest.raises(ValueError):
            ThreatAssessment(severity=15)


class TestScorer:
    def test_threat_score(self):
        s = calculate_threat_score(80, 5, 10, 8, 30)
        assert 0 <= s <= 100

    def test_score_zero(self):
        assert calculate_threat_score(0, 0, 0, 0, 0) == 0

    def test_score_max(self):
        assert calculate_threat_score(100, 10, 10, 10, 100) <= 100

    def test_deterministic(self):
        kw = {
            "incident_confidence": 70,
            "matched_stages": 5,
            "total_stages": 10,
            "max_severity": 7,
            "modifier": 20,
        }
        assert calculate_threat_score(**kw) == calculate_threat_score(**kw)

    def test_confidence(self):
        c = calculate_confidence(50, 10, 5)
        assert 0 <= c <= 100

    def test_confidence_bounded(self):
        assert calculate_confidence(100, 100, 100) <= 100

    def test_severity_max(self):
        assert calculate_severity(5, 8) == 8
        assert calculate_severity(9, 3) == 9

    def test_severity_bounded(self):
        assert calculate_severity(15, 20) == 10

    def test_classify_risk(self):
        assert classify_risk(10) == RiskLevel.INFORMATIONAL
        assert classify_risk(30) == RiskLevel.LOW
        assert classify_risk(50) == RiskLevel.MEDIUM
        assert classify_risk(70) == RiskLevel.HIGH
        assert classify_risk(90) == RiskLevel.CRITICAL

    def test_risk_boundaries(self):
        assert classify_risk(20) == RiskLevel.INFORMATIONAL
        assert classify_risk(21) == RiskLevel.LOW

    def test_recommend_critical(self):
        a, _r = recommend_action(RiskLevel.CRITICAL, 80, True)
        assert a == RecommendedAction.PERMANENT_BAN

    def test_recommend_high(self):
        a, _r = recommend_action(RiskLevel.HIGH, 60, True)
        assert a == RecommendedAction.TEMPORARY_BAN

    def test_recommend_medium(self):
        a, _r = recommend_action(RiskLevel.MEDIUM, 50, False)
        assert a in (RecommendedAction.NOTIFY_ADMIN, RecommendedAction.MONITOR)


class TestActions:
    def test_names(self):
        assert action_name(RecommendedAction.IGNORE) == "Ignore"
        assert action_name(RecommendedAction.PERMANENT_BAN) == "Permanent Ban"

    def test_attention(self):
        assert action_requires_attention(RecommendedAction.PERMANENT_BAN)
        assert not action_requires_attention(RecommendedAction.IGNORE)


class TestThreatEngine:
    def test_assess_completed(self):
        engine = ThreatEngine()
        incident = make_incident()
        a = engine.assess(
            incident,
            chain_severity=8,
            chain_confidence=20,
            matched_rule_severities=[5, 7, 6],
        )
        assert a is not None
        assert a.incident_id == "inc-001"

    def test_assess_expired(self):
        engine = ThreatEngine()
        incident = make_incident(state=IncidentState.EXPIRED, confidence_modifier=10)
        a = engine.assess(incident)
        assert a is not None
        assert a.risk_level in (RiskLevel.INFORMATIONAL, RiskLevel.LOW)

    def test_assess_batch(self):
        engine = ThreatEngine()
        results = engine.assess_batch([make_incident(), make_incident()])
        assert len(results) == 2

    def test_deterministic(self):
        engine = ThreatEngine()
        inc = make_incident()
        a1 = engine.assess(inc, chain_severity=7, chain_confidence=15)
        a2 = engine.assess(inc, chain_severity=7, chain_confidence=15)
        assert a1 is not None and a2 is not None
        assert a1.threat_score == a2.threat_score
        assert a1.risk_level == a2.risk_level

    def test_metrics(self):
        engine = ThreatEngine()
        engine.assess(make_incident())
        snap = engine.metrics_snapshot()
        assert snap.total_assessments >= 1


class TestBenchmarks:
    @pytest.mark.benchmark
    def test_throughput(self):
        engine = ThreatEngine()
        inc = make_incident()
        n = 10000
        t = time.monotonic()
        for _ in range(n):
            engine.assess(inc, chain_severity=7, chain_confidence=15)
        elapsed = time.monotonic() - t
        print(f"\n  Throughput: {n / elapsed:.0f} threats/s ({n} in {elapsed:.3f}s)")

    @pytest.mark.benchmark
    def test_latency(self):
        engine = ThreatEngine()
        inc = make_incident()
        lats = []
        for _ in range(100):
            t = time.monotonic()
            engine.assess(inc, chain_severity=7, chain_confidence=15)
            lats.append((time.monotonic() - t) * 1000)
        avg = sum(lats) / len(lats)
        print(f"\n  Latency: avg={avg:.4f}ms")
