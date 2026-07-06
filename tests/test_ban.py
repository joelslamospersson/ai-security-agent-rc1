"""
Comprehensive tests for the Ban Engine.
"""

from __future__ import annotations

import time

import pytest

from security_agent.ban import BanAction, BanDecision, BanEngine, BanLevel
from security_agent.ban.decision import make_decision
from security_agent.ban.escalation import calculate_escalation, get_duration
from security_agent.ban.history import BanHistory
from security_agent.ban.policy import BanPolicy, get_policy


class TestBanDecision:
    def test_creation(self) -> None:
        d = BanDecision(entity="1.2.3.4", threat_score=80, confidence=90)
        assert d.entity == "1.2.3.4"
        assert d.threat_score == 80

    def test_frozen(self) -> None:
        d = BanDecision()
        with pytest.raises(AttributeError):
            d.entity = "x"  # type: ignore[misc]

    def test_invalid_threat(self) -> None:
        with pytest.raises(ValueError):
            BanDecision(threat_score=150)

    def test_invalid_confidence(self) -> None:
        with pytest.raises(ValueError):
            BanDecision(confidence=150)


class TestBanLevel:
    def test_durations(self) -> None:
        assert get_duration(BanLevel.WARNING) == 0
        assert get_duration(BanLevel.BAN_30M) == 1800
        assert get_duration(BanLevel.BAN_1H) == 3600
        assert get_duration(BanLevel.BAN_7D) == 604800
        assert get_duration(BanLevel.PERMANENT) == 0


class TestBanHistory:
    def test_record_ban(self) -> None:
        h = BanHistory()
        r = h.record_ban("1.2.3.4", "ipv4", 1, 1800)
        assert r.total_bans == 1
        assert r.active_level == 1

    def test_lookup(self) -> None:
        h = BanHistory()
        assert h.lookup("1.2.3.4", "ipv4") is None
        h.record_ban("1.2.3.4", "ipv4", 1, 1800)
        assert h.lookup("1.2.3.4", "ipv4") is not None

    def test_increment(self) -> None:
        h = BanHistory()
        h.record_ban("1.2.3.4", "ipv4", 1, 1800)
        h.record_ban("1.2.3.4", "ipv4", 2, 3600)
        r = h.lookup("1.2.3.4", "ipv4")
        assert r is not None
        assert r.total_bans == 2
        assert r.active_level == 2


class TestEscalation:
    def test_balanced_low_threat(self) -> None:
        p = get_policy(BanPolicy.BALANCED)
        lv, _ = calculate_escalation(10, 50, 0, 0, False, False, False, p)
        assert lv == BanLevel.WARNING

    def test_balanced_high_threat(self) -> None:
        p = get_policy(BanPolicy.BALANCED)
        lv, _ = calculate_escalation(85, 90, 0, 0, False, False, False, p)
        assert lv >= BanLevel.BAN_24H

    def test_balanced_critical(self) -> None:
        p = get_policy(BanPolicy.BALANCED)
        _, perm = calculate_escalation(95, 95, 0, 0, False, False, False, p)
        assert perm

    def test_repeat_escalates(self) -> None:
        p = get_policy(BanPolicy.BALANCED)
        lv1, _ = calculate_escalation(70, 80, 0, 0, False, False, False, p)
        lv2, _ = calculate_escalation(70, 80, 3, -60, True, False, False, p)
        assert lv2 >= lv1

    def test_whitelist_never_banned(self) -> None:
        p = get_policy(BanPolicy.BALANCED)
        lv, _ = calculate_escalation(95, 95, 0, 0, False, True, False, p)
        assert lv == BanLevel.WARNING

    def test_conservative_no_permanent(self) -> None:
        p = get_policy(BanPolicy.CONSERVATIVE)
        _, perm = calculate_escalation(95, 95, 5, -80, True, False, False, p)
        assert not perm

    def test_policy_thresholds(self) -> None:
        """Aggressive bans at lower thresholds than balanced."""
        bal = get_policy(BanPolicy.BALANCED)
        agg = get_policy(BanPolicy.AGGRESSIVE)
        assert agg.min_threat_score < bal.min_threat_score


class TestDecision:
    def test_whitelist_skip(self) -> None:
        d = make_decision(
            "1.2.3.4", "ipv4", 90, 95, -80, "c", BanHistory(), whitelisted=True
        )
        assert d.action == BanAction.WHITELIST_SKIP

    def test_exemption_skip(self) -> None:
        d = make_decision(
            "1.2.3.4", "ipv4", 90, 95, -80, "c", BanHistory(), exempt=True
        )
        assert d.action == BanAction.EXEMPTION_SKIP

    def test_warning(self) -> None:
        d = make_decision("1.2.3.4", "ipv4", 10, 50, 0, "c", BanHistory())
        assert d.action == BanAction.WARNING

    def test_temporary_ban(self) -> None:
        d = make_decision("1.2.3.4", "ipv4", 70, 80, -30, "c", BanHistory())
        assert d.action == BanAction.TEMPORARY_BAN

    def test_permanent_ban(self) -> None:
        d = make_decision("1.2.3.4", "ipv4", 95, 95, -80, "c", BanHistory())
        assert d.action == BanAction.PERMANENT_BAN

    def test_deterministic(self) -> None:
        h = BanHistory()
        d1 = make_decision("1.2.3.4", "ipv4", 75, 85, -40, "c", h)
        d2 = make_decision("1.2.3.4", "ipv4", 75, 85, -40, "c", h)
        assert d1.escalation_level == d2.escalation_level
        assert d1.action == d2.action


class TestBanEngine:
    def test_decide(self) -> None:
        engine = BanEngine()
        d = engine.decide("1.2.3.4", "ipv4", 70, 80, -30, "corr")
        assert d.entity == "1.2.3.4"

    def test_whitelist(self) -> None:
        engine = BanEngine()
        engine.whitelist_add("1.1.1.1")
        d = engine.decide("1.1.1.1", "ipv4", 95, 95, -90)
        assert d.action == BanAction.WHITELIST_SKIP

    def test_exemption(self) -> None:
        engine = BanEngine()
        engine.exemption_add("10.0.0.1")
        d = engine.decide("10.0.0.1", "ipv4", 95, 95, -90)
        assert d.action == BanAction.EXEMPTION_SKIP

    def test_repeat_tracked(self) -> None:
        engine = BanEngine()
        engine.decide("1.2.3.4", "ipv4", 70, 80, -30)
        engine.decide("1.2.3.4", "ipv4", 70, 80, -30)
        h = engine.get_ban_history("1.2.3.4", "ipv4")
        assert h is not None
        assert h.total_bans >= 2

    def test_metrics(self) -> None:
        engine = BanEngine()
        engine.decide("1.2.3.4", "ipv4", 70, 80, -30)
        engine.decide("5.6.7.8", "ipv4", 95, 95, -80)
        s = engine.metrics_snapshot()
        assert s.total_decisions >= 2


class TestBenchmarks:
    @pytest.mark.benchmark
    def test_throughput(self) -> None:
        engine = BanEngine()
        n = 10000
        t = time.monotonic()
        for i in range(n):
            engine.decide(f"10.0.0.{i % 256}", "ipv4", 60, 70, -20)
        elapsed = time.monotonic() - t
        print(f"\n  Throughput: {n / elapsed:.0f} decisions/s ({n} in {elapsed:.3f}s)")

    @pytest.mark.benchmark
    def test_latency(self) -> None:
        p = get_policy(BanPolicy.BALANCED)
        lats = []
        for _ in range(100):
            t = time.monotonic()
            calculate_escalation(70, 80, 2, -40, True, False, False, p)
            lats.append((time.monotonic() - t) * 1000)
        avg = sum(lats) / len(lats)
        print(f"\n  Escalation latency: avg={avg:.4f}ms")
