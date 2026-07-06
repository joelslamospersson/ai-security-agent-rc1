"""
Comprehensive tests for the Reputation Engine.
"""

from __future__ import annotations

import time

import pytest

from security_agent.reputation import EntityType, ReputationEngine, ReputationRecord
from security_agent.reputation.decay import calculate_decay
from security_agent.reputation.manager import ReputationManager
from security_agent.reputation.scoring import calculate_score_change, clamp_score
from security_agent.reputation.store import ReputationStore


class TestReputationRecord:
    def test_creation(self) -> None:
        r = ReputationRecord(
            entity_type=EntityType.IPV4, entity_value="1.2.3.4", current_score=50
        )
        assert r.entity_value == "1.2.3.4"
        assert r.current_score == 50

    def test_frozen(self) -> None:
        r = ReputationRecord(entity_value="x")
        with pytest.raises(AttributeError):
            r.current_score = 50  # type: ignore[misc]

    def test_default_score(self) -> None:
        r = ReputationRecord()
        assert r.current_score == 0

    def test_invalid_score(self) -> None:
        with pytest.raises(ValueError):
            ReputationRecord(current_score=200)


class TestStore:
    def test_lookup_missing(self) -> None:
        store = ReputationStore()
        assert store.lookup(EntityType.IPV4, "1.2.3.4") is None

    def test_upsert_create(self) -> None:
        store = ReputationStore()
        r = store.upsert(EntityType.IPV4, "1.2.3.4", -30, 80)
        assert r.current_score == -30
        assert r.event_count == 1

    def test_upsert_update(self) -> None:
        store = ReputationStore()
        store.upsert(EntityType.IPV4, "1.2.3.4", -30, 80)
        r = store.upsert(EntityType.IPV4, "1.2.3.4", -50, 90)
        assert r.current_score == -50
        assert r.event_count == 2

    def test_exists(self) -> None:
        store = ReputationStore()
        assert not store.exists(EntityType.IPV4, "1.2.3.4")
        store.upsert(EntityType.IPV4, "1.2.3.4", 0, 50)
        assert store.exists(EntityType.IPV4, "1.2.3.4")

    def test_count(self) -> None:
        store = ReputationStore()
        assert store.count() == 0
        store.upsert(EntityType.IPV4, "1.2.3.4", 0, 50)
        store.upsert(EntityType.IPV6, "::1", 0, 50)
        assert store.count() == 2

    def test_list_by_type(self) -> None:
        store = ReputationStore()
        store.upsert(EntityType.IPV4, "1.1.1.1", 0, 50)
        store.upsert(EntityType.IPV4, "2.2.2.2", 0, 50)
        store.upsert(EntityType.USERNAME, "admin", 0, 50)
        assert len(store.list_by_type(EntityType.IPV4)) == 2
        assert len(store.list_by_type(EntityType.USERNAME)) == 1


class TestScoring:
    def test_score_change_negative(self) -> None:
        c = calculate_score_change(
            threat_score=80, confidence=90, risk_level=3, is_repeat=False, ban_count=0
        )
        assert c < 0

    def test_score_change_repeat(self) -> None:
        single = calculate_score_change(50, 70, 2, False, 0)
        repeat = calculate_score_change(50, 70, 2, True, 0)
        assert repeat <= single

    def test_score_change_ban_history(self) -> None:
        no_bans = calculate_score_change(50, 70, 2, False, 0)
        with_bans = calculate_score_change(50, 70, 2, False, 5)
        assert with_bans <= no_bans

    def test_clamp(self) -> None:
        assert clamp_score(200) == 100
        assert clamp_score(-200) == -100
        assert clamp_score(50) == 50


class TestDecay:
    def test_decay_positive(self) -> None:
        d = calculate_decay(
            current_score=50, last_seen=time.time() - 86400 * 2, hours_per_point=24
        )
        assert d < 50 and d >= 0

    def test_decay_negative(self) -> None:
        d = calculate_decay(
            current_score=-50, last_seen=time.time() - 86400 * 2, hours_per_point=24
        )
        assert d > -50 and d <= 0

    def test_no_decay_recent(self) -> None:
        d = calculate_decay(current_score=50, last_seen=time.time())
        assert d == 50

    def test_permanent_no_decay(self) -> None:
        d = calculate_decay(
            current_score=-100, last_seen=time.time() - 86400 * 30, is_permanent=True
        )
        assert d == -100

    def test_no_decay_at_zero(self) -> None:
        d = calculate_decay(current_score=0, last_seen=0)
        assert d == 0


class TestManager:
    def test_process_threat_creates(self) -> None:
        store = ReputationStore()
        mgr = ReputationManager(store)
        r = mgr.process_threat(EntityType.IPV4, "1.2.3.4", 80, 90, 3)
        assert r is not None
        assert r.current_score < 0

    def test_process_threat_updates(self) -> None:
        store = ReputationStore()
        mgr = ReputationManager(store)
        mgr.process_threat(EntityType.IPV4, "1.2.3.4", 50, 70, 2)
        r = mgr.process_threat(EntityType.IPV4, "1.2.3.4", 90, 95, 4)
        assert r.event_count == 2

    def test_process_positive(self) -> None:
        store = ReputationStore()
        mgr = ReputationManager(store)
        r = mgr.process_positive(EntityType.IPV4, "1.2.3.4", 10)
        assert r.current_score == 10


class TestEngine:
    def test_process_threat(self) -> None:
        engine = ReputationEngine()
        r = engine.process_threat(EntityType.IPV4, "1.2.3.4", 80, 90, 3)
        assert r is not None
        assert r.current_score < 0

    def test_get_reputation(self) -> None:
        engine = ReputationEngine()
        assert engine.get_reputation(EntityType.IPV4, "1.2.3.4") is None
        engine.process_threat(EntityType.IPV4, "1.2.3.4", 50, 70, 2)
        assert engine.get_reputation(EntityType.IPV4, "1.2.3.4") is not None

    def test_exists(self) -> None:
        engine = ReputationEngine()
        assert not engine.exists(EntityType.IPV4, "1.2.3.4")
        engine.process_threat(EntityType.IPV4, "1.2.3.4", 50, 70, 2)
        assert engine.exists(EntityType.IPV4, "1.2.3.4")

    def test_multiple_entity_types(self) -> None:
        engine = ReputationEngine()
        engine.process_threat(EntityType.IPV4, "1.2.3.4", 80, 90, 3)
        engine.process_threat(EntityType.USERNAME, "admin", 60, 80, 2)
        engine.process_threat(EntityType.HOSTNAME, "server1", 40, 60, 1)
        assert engine.exists(EntityType.IPV4, "1.2.3.4")
        assert engine.exists(EntityType.USERNAME, "admin")
        assert engine.exists(EntityType.HOSTNAME, "server1")
        assert engine.list_all().__len__() == 3

    def test_apply_decay(self) -> None:
        engine = ReputationEngine()
        engine.process_threat(EntityType.IPV4, "1.2.3.4", 80, 90, 3)
        count = engine.apply_decay()
        assert count >= 0

    def test_metrics(self) -> None:
        engine = ReputationEngine()
        engine.process_threat(EntityType.IPV4, "1.2.3.4", 80, 90, 3)
        snap = engine.metrics_snapshot()
        assert snap.total_entities > 0
        assert snap.avg_score < 0


class TestBenchmarks:
    @pytest.mark.benchmark
    def test_10000_entities(self) -> None:
        engine = ReputationEngine()
        t = time.monotonic()
        for i in range(10000):
            engine.process_threat(
                EntityType.IPV4, f"10.0.0.{i % 256}", 50 + (i % 50), 70, 2
            )
        elapsed = time.monotonic() - t
        print(f"\n  10000 entities in {elapsed:.3f}s ({10000 / elapsed:.0f} updates/s)")

    @pytest.mark.benchmark
    def test_lookup_latency(self) -> None:
        engine = ReputationEngine()
        for i in range(1000):
            engine.process_threat(EntityType.IPV4, f"10.0.0.{i % 256}", 50, 70, 2)
        t = time.monotonic()
        for i in range(1000):
            engine.get_reputation(EntityType.IPV4, f"10.0.0.{i % 256}")
        elapsed = time.monotonic() - t
        print(f"\n  1000 lookups in {elapsed:.3f}s ({1000 / elapsed:.0f} lookups/s)")
