"""
Comprehensive tests for the Detection Framework.
"""

from __future__ import annotations

import time

import pytest

from security_agent.detectors import (
    DetectionResult,
    DetectorCapabilities,
    DetectorContext,
    DetectorManager,
    DetectorNotFoundError,
    DetectorRegistrationError,
    DetectorRegistry,
)
from security_agent.detectors.base import Detector
from security_agent.events import EventType, SecurityEvent


class PassDetector(Detector):  # type: ignore[misc]
    def __init__(self, name: str = "pass") -> None:
        super().__init__(detector_id=name, name=name)
        self.init_called = False
        self.shutdown_called = False
        self.analyze_count = 0

    async def initialize(self) -> None:
        await super().initialize()
        self.init_called = True

    async def analyze(
        self,
        _event: SecurityEvent,
        _ctx: DetectorContext,
    ) -> list[DetectionResult]:
        self.analyze_count += 1
        return []

    async def shutdown(self) -> None:
        await super().shutdown()
        self.shutdown_called = True

    def capabilities(self) -> DetectorCapabilities:
        return DetectorCapabilities(event_types=(EventType.SECURITY_EVENT,))


class HitDetector(Detector):  # type: ignore[misc]
    def __init__(
        self, name: str = "hit", confidence: int = 85, severity: int = 7
    ) -> None:
        super().__init__(detector_id=name, name=name)
        self._confidence = confidence
        self._severity = severity

    async def analyze(
        self,
        event: SecurityEvent,
        ctx: DetectorContext,
    ) -> list[DetectionResult]:
        return [
            DetectionResult(
                detector_id=self.detector_id,
                detector_name=self.name,
                event_id=event.event_id,
                correlation_id=ctx.correlation_id,
                confidence=self._confidence,
                severity=self._severity,
                threat_score=60,
                threat_type="test_threat",
                evidence=f"Detected by {self.name}",
            ),
        ]

    def capabilities(self) -> DetectorCapabilities:
        return DetectorCapabilities(event_types=(EventType.SECURITY_EVENT,))


class FailDetector(Detector):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__(detector_id="fail", name="fail")

    async def analyze(
        self,
        event: SecurityEvent,
        _ctx: DetectorContext,
    ) -> list[DetectionResult]:
        raise RuntimeError(f"Analysis failure for {event.event_id}")

    def capabilities(self) -> DetectorCapabilities:
        return DetectorCapabilities(event_types=(EventType.SECURITY_EVENT,))


class SkipDetector(Detector):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__(detector_id="skip", name="skip")

    async def analyze(
        self,
        _event: SecurityEvent,
        _ctx: DetectorContext,
    ) -> list[DetectionResult]:
        return [
            DetectionResult(
                detector_name="skip", confidence=50, severity=5, threat_score=25
            )
        ]

    def capabilities(self) -> DetectorCapabilities:
        return DetectorCapabilities(event_types=(EventType.INTERNAL_METRICS,))


class InitFailDetector(Detector):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__(detector_id="failinit", name="failinit")

    async def initialize(self) -> None:
        raise RuntimeError("Init failure")

    async def analyze(
        self,
        _event: SecurityEvent,
        _ctx: DetectorContext,
    ) -> list[DetectionResult]:
        return [
            DetectionResult(
                detector_name="failinit", confidence=50, severity=5, threat_score=25
            )
        ]

    def capabilities(self) -> DetectorCapabilities:
        return DetectorCapabilities(event_types=(EventType.SECURITY_EVENT,))


class TestDetectionResult:
    def test_creation(self) -> None:
        r = DetectionResult(
            detector_name="test", confidence=75, severity=5, threat_score=50
        )
        assert r.detector_name == "test"
        assert r.confidence == 75
        assert r.severity == 5

    def test_frozen(self) -> None:
        r = DetectionResult()
        with pytest.raises(AttributeError):
            r.confidence = 50  # type: ignore[misc]

    def test_invalid_confidence_raises(self) -> None:
        with pytest.raises(ValueError):
            DetectionResult(confidence=150)

    def test_invalid_severity_raises(self) -> None:
        with pytest.raises(ValueError):
            DetectionResult(severity=15)

    def test_invalid_threat_score_raises(self) -> None:
        with pytest.raises(ValueError):
            DetectionResult(threat_score=200)


class TestDetectorInterface:
    @pytest.mark.asyncio
    async def test_initialize(self) -> None:
        d = PassDetector("test_detector")
        assert not d.is_initialized
        await d.initialize()
        assert d.is_initialized
        assert d.init_called

    @pytest.mark.asyncio
    async def test_shutdown(self) -> None:
        d = PassDetector()
        await d.initialize()
        await d.shutdown()
        assert not d.is_initialized
        assert d.shutdown_called

    @pytest.mark.asyncio
    async def test_analyze_returns_list(self) -> None:
        d = PassDetector()
        results = await d.analyze(SecurityEvent(), DetectorContext())
        assert isinstance(results, list)

    def test_enable_disable(self) -> None:
        d = PassDetector()
        assert d.is_enabled
        d.disable()
        assert not d.is_enabled
        d.enable()
        assert d.is_enabled

    def test_capabilities(self) -> None:
        d = PassDetector()
        caps = d.capabilities()
        assert isinstance(caps, DetectorCapabilities)


class TestDetectorRegistry:
    def test_register_and_lookup(self) -> None:
        reg = DetectorRegistry()
        d = PassDetector("d1")
        reg.register(d)
        assert reg.lookup("d1") is d
        assert reg.count == 1

    def test_duplicate_raises(self) -> None:
        reg = DetectorRegistry()
        reg.register(PassDetector("d1"))
        with pytest.raises(DetectorRegistrationError):
            reg.register(PassDetector("d1"))

    def test_empty_name_raises(self) -> None:
        reg = DetectorRegistry()
        with pytest.raises(DetectorRegistrationError):
            reg.register(PassDetector(""))

    def test_unregister(self) -> None:
        reg = DetectorRegistry()
        reg.register(PassDetector("d1"))
        reg.unregister("d1")
        assert reg.count == 0

    def test_unregister_nonexistent_raises(self) -> None:
        reg = DetectorRegistry()
        with pytest.raises(DetectorNotFoundError):
            reg.unregister("x")

    def test_enable_disable(self) -> None:
        reg = DetectorRegistry()
        reg.register(PassDetector("d1"))
        assert reg.is_enabled("d1")
        reg.disable("d1")
        assert not reg.is_enabled("d1")
        reg.enable("d1")
        assert reg.is_enabled("d1")

    def test_list_enabled(self) -> None:
        reg = DetectorRegistry()
        reg.register(PassDetector("d1"))
        reg.register(PassDetector("d2"))
        reg.disable("d1")
        enabled = reg.list_enabled()
        assert len(enabled) == 1
        assert enabled[0].name == "d2"

    def test_clear(self) -> None:
        reg = DetectorRegistry()
        reg.register(PassDetector("d1"))
        reg.clear()
        assert reg.count == 0


class TestDetectorManager:
    @pytest.mark.asyncio
    async def test_initialize_all(self) -> None:
        reg = DetectorRegistry()
        reg.register(PassDetector("d1"))
        reg.register(PassDetector("d2"))
        manager = DetectorManager(reg)
        await manager.initialize_all()
        assert manager.is_initialized

    @pytest.mark.asyncio
    async def test_analyze_empty_when_no_detectors(self) -> None:
        reg = DetectorRegistry()
        manager = DetectorManager(reg)
        results = await manager.analyze(SecurityEvent())
        assert results == []

    @pytest.mark.asyncio
    async def test_analyze_returns_results(self) -> None:
        reg = DetectorRegistry()
        reg.register(HitDetector("hit"))
        manager = DetectorManager(reg)
        await manager.initialize_all()
        results = await manager.analyze(SecurityEvent())
        assert len(results) == 1
        assert results[0].detector_name == "hit"
        assert results[0].confidence == 85

    @pytest.mark.asyncio
    async def test_fail_init_disables_detector(self) -> None:
        reg = DetectorRegistry()
        reg.register(InitFailDetector())
        reg.register(PassDetector("good"))
        manager = DetectorManager(reg)
        await manager.initialize_all()
        assert not reg.is_enabled("failinit")
        assert reg.is_enabled("good")

    @pytest.mark.asyncio
    async def test_fail_analysis_isolated(self) -> None:
        reg = DetectorRegistry()
        reg.register(HitDetector("good1"))
        reg.register(FailDetector())
        reg.register(HitDetector("good2"))
        manager = DetectorManager(reg)
        await manager.initialize_all()
        results = await manager.analyze(SecurityEvent())
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_skip_incompatible_detectors(self) -> None:
        reg = DetectorRegistry()
        reg.register(HitDetector("h1"))
        reg.register(SkipDetector())
        reg.register(HitDetector("h2"))
        manager = DetectorManager(reg)
        await manager.initialize_all()
        results = await manager.analyze(SecurityEvent())
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_metrics(self) -> None:
        reg = DetectorRegistry()
        reg.register(HitDetector("h1"))
        reg.register(HitDetector("h2"))
        manager = DetectorManager(reg)
        await manager.initialize_all()
        await manager.analyze(SecurityEvent())
        snap = manager.metrics_snapshot()
        assert snap.events_analyzed >= 1
        assert snap.detections_produced >= 1

    @pytest.mark.asyncio
    async def test_shutdown_all(self) -> None:
        reg = DetectorRegistry()
        d = PassDetector("d1")
        reg.register(d)
        manager = DetectorManager(reg)
        await manager.initialize_all()
        await manager.shutdown_all()
        assert d.shutdown_called


class TestBenchmarks:
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_framework_overhead(self) -> None:
        reg = DetectorRegistry()
        for i in range(10):
            reg.register(PassDetector(f"d{i}"))
        manager = DetectorManager(reg)
        await manager.initialize_all()
        count = 500
        start = time.monotonic()
        for _ in range(count):
            await manager.analyze(SecurityEvent())
        elapsed = time.monotonic() - start
        print(f"\n  Framework: {count / elapsed:.0f} ev/s ({count} in {elapsed:.3f}s)")

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_detector_latency(self) -> None:
        reg = DetectorRegistry()
        reg.register(HitDetector("bench"))
        manager = DetectorManager(reg)
        await manager.initialize_all()
        latencies: list[float] = []
        for _ in range(100):
            t = time.monotonic()
            await manager.analyze(SecurityEvent())
            latencies.append((time.monotonic() - t) * 1000)
        avg = sum(latencies) / len(latencies)
        print(f"\n  Latency: avg={avg:.3f}ms")
