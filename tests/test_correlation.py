"""
Comprehensive tests for the Correlation Engine.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import pytest

from security_agent.correlation import (
    AttackChain,
    ChainStage,
    CorrelationEngine,
    CorrelationKey,
    StageType,
)
from security_agent.correlation.chain import ChainTracker
from security_agent.correlation.incident import IncidentManager
from security_agent.correlation.loader import _dict_to_chain, load_chains
from security_agent.correlation.matcher import extract_key_value
from security_agent.correlation.models import ActiveChain, IncidentState
from security_agent.correlation.validator import validate_chains


@dataclass
class FakeRuleMatch:
    rule_id: str = ""
    event_id: str = ""
    correlation_id: str = ""


SAMPLE_CHAIN = AttackChain(
    id="chain-test",
    name="Test Chain",
    enabled=True,
    correlation_key=CorrelationKey.SOURCE_IP,
    timeout=3600,
    stages=(
        ChainStage(
            stage_id="s1", stage_type=StageType.ORDERED, rule_ids=("r1",), timeout=300
        ),
        ChainStage(
            stage_id="s2", stage_type=StageType.ORDERED, rule_ids=("r2",), timeout=300
        ),
        ChainStage(
            stage_id="s3", stage_type=StageType.ORDERED, rule_ids=("r3",), timeout=300
        ),
    ),
)


class TestAttackChain:
    def test_chain_creation(self) -> None:
        c = AttackChain(id="c1", name="test")
        assert c.id == "c1"
        assert c.stages == ()

    def test_chain_frozen(self) -> None:
        c = AttackChain(id="c1", name="test")
        with pytest.raises(AttributeError):
            c.id = "x"  # type: ignore[misc]


class TestChainTracker:
    def test_start_chain(self) -> None:
        tracker = ChainTracker()
        active = tracker.start_chain(SAMPLE_CHAIN, "1.2.3.4")
        assert active.chain_id == "chain-test"
        assert active.key_value == "1.2.3.4"
        assert not active.completed
        assert tracker.active_count == 1

    def test_advance_ordered(self) -> None:
        tracker = ChainTracker()
        active = tracker.start_chain(SAMPLE_CHAIN, "1.2.3.4")
        completed = tracker.advance(SAMPLE_CHAIN, active, "r1", "ev1")
        assert not completed
        assert active.current_stage_index == 1

        completed = tracker.advance(SAMPLE_CHAIN, active, "r2", "ev2")
        assert not completed
        assert active.current_stage_index == 2

        completed = tracker.advance(SAMPLE_CHAIN, active, "r3", "ev3")
        assert completed
        assert active.current_stage_index == 3

    def test_advance_out_of_order(self) -> None:
        """Ordered stage should not match if not current stage."""
        tracker = ChainTracker()
        active = tracker.start_chain(SAMPLE_CHAIN, "1.2.3.4")
        completed = tracker.advance(SAMPLE_CHAIN, active, "r2", "ev2")
        assert not completed
        assert active.current_stage_index == 0  # r2 didn't advance

    def test_optional_stage(self) -> None:
        chain = AttackChain(
            id="c1",
            name="test",
            stages=(
                ChainStage(
                    stage_id="required",
                    stage_type=StageType.ORDERED,
                    rule_ids=("r1",),
                    timeout=300,
                ),
                ChainStage(
                    stage_id="optional",
                    stage_type=StageType.OPTIONAL,
                    rule_ids=("r2",),
                    timeout=300,
                ),
            ),
        )
        tracker = ChainTracker()
        active = tracker.start_chain(chain, "1.2.3.4")

        # Advance past required stage
        tracker.advance(chain, active, "r1", "ev1")
        assert active.current_stage_index == 1

        # Advance optional (should complete since all required done)
        completed = tracker.advance(chain, active, "r2", "ev2")
        assert completed

    def test_expiration(self) -> None:
        tracker = ChainTracker()
        chain = AttackChain(
            id="c1",
            name="test",
            timeout=1,
            stages=(
                ChainStage(
                    stage_id="s1",
                    stage_type=StageType.ORDERED,
                    rule_ids=("r1",),
                    timeout=1,
                ),
            ),
        )
        active = tracker.start_chain(chain, "1.2.3.4")
        assert not active.is_expired(chain.timeout, time.time())  # Just created

        # Fake old timestamp
        active.last_match_at = time.time() - 10
        assert active.is_expired(chain.timeout, time.time())

    @pytest.mark.asyncio
    async def test_expire_old(self) -> None:
        tracker = ChainTracker()
        chain_def = AttackChain(
            id="c1",
            name="test",
            timeout=1,
            stages=(ChainStage(stage_id="s1", rule_ids=("r1",)),),
        )
        tracker.start_chain(chain_def, "1.2.3.4")
        # Fake old timestamp
        for ac in tracker._chains.values():
            ac.last_match_at = time.time() - 10

        expired = await tracker.expire_old({"c1": chain_def})
        assert len(expired) == 1
        assert expired[0].expired
        assert tracker.active_count == 0


class TestCorrelationEngine:
    def test_load_chains(self) -> None:
        engine = CorrelationEngine()
        engine.load_chains([SAMPLE_CHAIN])
        assert engine.active_count == 0

    def test_correlate_no_match(self) -> None:
        engine = CorrelationEngine()
        engine.load_chains([SAMPLE_CHAIN])
        match = FakeRuleMatch(rule_id="unknown")
        incidents = engine.correlate(match, {"source_ip": "1.2.3.4"})
        assert incidents == []
        assert engine.active_count == 1  # Chain started

    def test_correlate_completes(self) -> None:
        engine = CorrelationEngine()
        engine.load_chains([SAMPLE_CHAIN])

        # Step through all 3 stages
        for i, rid in enumerate(["r1", "r2", "r3"]):
            match = FakeRuleMatch(rule_id=rid, event_id=f"ev{i}")
            incidents = engine.correlate(match, {"source_ip": "1.2.3.4"})
            if i < 2:
                assert incidents == []
            else:
                assert len(incidents) == 1
                assert incidents[0].state == IncidentState.COMPLETED

    def test_multiple_sources_independent(self) -> None:
        """Different IPs should not interfere."""
        engine = CorrelationEngine()
        engine.load_chains([SAMPLE_CHAIN])

        # Advance IP1 through stage 1
        engine.correlate(FakeRuleMatch(rule_id="r1"), {"source_ip": "1.1.1.1"})
        # Advance IP2 through stage 1
        engine.correlate(FakeRuleMatch(rule_id="r1"), {"source_ip": "2.2.2.2"})

        assert engine.active_count == 2

        # Complete IP1
        engine.correlate(FakeRuleMatch(rule_id="r2"), {"source_ip": "1.1.1.1"})
        engine.correlate(FakeRuleMatch(rule_id="r3"), {"source_ip": "1.1.1.1"})

        # IP2 should still be at stage 1
        assert engine.active_count == 1

    def test_metrics(self) -> None:
        engine = CorrelationEngine()
        engine.load_chains([SAMPLE_CHAIN])
        engine.correlate(FakeRuleMatch(rule_id="r1"), {"source_ip": "1.2.3.4"})

        snap = engine.metrics_snapshot()
        assert snap.chains_started >= 1
        assert snap.avg_latency_ms >= 0

    @pytest.mark.asyncio
    async def test_cleanup_expired(self) -> None:
        engine = CorrelationEngine()
        expired_chain = AttackChain(
            id="exp",
            name="exp",
            timeout=1,
            stages=(ChainStage(stage_id="s1", rule_ids=("r1",)),),
        )
        engine.load_chains([expired_chain])
        engine.correlate(FakeRuleMatch(rule_id="unknown"), {"source_ip": "1.2.3.4"})

        # Fake old timestamp
        for ac in engine._tracker._chains.values():
            ac.last_match_at = time.time() - 10

        incidents = await engine.cleanup_expired()
        assert len(incidents) == 1
        assert incidents[0].state == IncidentState.EXPIRED


class TestLoader:
    def test_dict_to_chain(self) -> None:
        d = {
            "id": "c1",
            "name": "test",
            "correlation_key": "source_ip",
            "stages": [{"stage_id": "s1", "rule_ids": ["r1"]}],
        }
        chain = _dict_to_chain(d)
        assert chain.id == "c1"
        assert len(chain.stages) == 1

    def test_load_attack_chains_yaml(self) -> None:
        chains = load_chains("correlation/attack_chains.yaml")
        assert len(chains) >= 3

    def test_load_nonexistent_raises(self) -> None:
        from security_agent.correlation.exceptions import ChainLoadError

        with pytest.raises(ChainLoadError):
            load_chains("correlation/nonexistent.yaml")


class TestValidator:
    def test_valid_chain_passes(self) -> None:
        chains = [
            {
                "id": "c1",
                "name": "test",
                "correlation_key": "source_ip",
                "stages": [{"stage_id": "s1", "rule_ids": ["r1"]}],
            }
        ]
        errors = validate_chains(chains)
        assert errors == []

    def test_duplicate_id_fails(self) -> None:
        chains = [
            {
                "id": "c1",
                "name": "a",
                "stages": [{"stage_id": "s1", "rule_ids": ["r1"]}],
            },
            {
                "id": "c1",
                "name": "b",
                "stages": [{"stage_id": "s2", "rule_ids": ["r2"]}],
            },
        ]
        errors = validate_chains(chains)
        assert any("Duplicate" in e for e in errors)

    def test_invalid_correlation_key_fails(self) -> None:
        chains = [
            {
                "id": "c1",
                "name": "test",
                "correlation_key": "invalid_key",
                "stages": [{"stage_id": "s1", "rule_ids": ["r1"]}],
            }
        ]
        errors = validate_chains(chains)
        assert any("correlation_key" in e for e in errors)

    def test_missing_stages_fails(self) -> None:
        chains = [{"id": "c1", "name": "test"}]
        errors = validate_chains(chains)
        assert any("stages" in e for e in errors)

    def test_empty_rule_ids_fails(self) -> None:
        chains = [
            {
                "id": "c1",
                "name": "test",
                "stages": [{"stage_id": "s1", "rule_ids": []}],
            }
        ]
        errors = validate_chains(chains)
        assert any("rule_ids" in e for e in errors)


class TestMatcher:
    def test_extract_source_ip(self) -> None:
        v = extract_key_value(
            CorrelationKey.SOURCE_IP, FakeRuleMatch(), {"source_ip": "1.2.3.4"}
        )
        assert v == "1.2.3.4"

    def test_extract_correlation_id(self) -> None:
        v = extract_key_value(
            CorrelationKey.CORRELATION_ID, FakeRuleMatch(correlation_id="abc")
        )
        assert v == "abc"

    def test_extract_unknown(self) -> None:
        v = extract_key_value(CorrelationKey.HOSTNAME, FakeRuleMatch(), {})
        assert v == "unknown"


class TestIncidentManager:
    def test_create_incident(self) -> None:
        mgr = IncidentManager()
        active = ActiveChain(chain_id="c1", key_value="1.2.3.4")
        chain = AttackChain(
            id="c1", name="test", stages=(ChainStage(stage_id="s1", rule_ids=("r1",)),)
        )
        incident = mgr.create_incident(chain, active)
        assert incident.state == IncidentState.COMPLETED


class TestBenchmarks:
    @pytest.mark.benchmark
    def test_1000_chains_overhead(self) -> None:
        """Measure correlation engine overhead with 1000 active chains."""
        engine = CorrelationEngine()
        chain = AttackChain(
            id="c1",
            name="bench",
            stages=(
                ChainStage(
                    stage_id="s1",
                    rule_ids=("r1",),
                    stage_type=StageType.ORDERED,
                    timeout=300,
                ),
            ),
        )
        engine.load_chains([chain])

        # Start 1000 chains
        for i in range(1000):
            engine.correlate(
                FakeRuleMatch(rule_id="x"), {"source_ip": f"10.0.{i // 255}.{i % 255}"}
            )

        assert engine.active_count == 1000
        print(f"\n  1000 active chains: {engine.active_count}")

    @pytest.mark.benchmark
    def test_correlation_throughput(self) -> None:
        """Measure rule match correlation throughput."""
        import time

        engine = CorrelationEngine()
        engine.load_chains([SAMPLE_CHAIN])

        match = FakeRuleMatch(rule_id="r1", event_id="ev1")

        count = 5000
        t = time.monotonic()
        for i in range(count):
            engine.correlate(match, {"source_ip": f"10.0.{i // 255}.{i % 255}"})
        elapsed = time.monotonic() - t
        throughput = count / elapsed
        print(
            f"\n  Correlation throughput: {throughput:.0f} matches/s ({count} in {elapsed:.2f}s)"
        )
