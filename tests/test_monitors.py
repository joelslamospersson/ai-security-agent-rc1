"""
Comprehensive tests for the Monitor Framework.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from security_agent.event_bus import EventBus
from security_agent.monitors import (
    HealthReport,
    HealthState,
    MonitorContext,
    MonitorManager,
    MonitorNotFoundError,
    MonitorRegistrationError,
    MonitorRegistry,
)
from security_agent.monitors.base import Monitor
from security_agent.monitors.events import (
    monitor_failed,
    monitor_health_changed,
    monitor_started,
    monitor_stopped,
)


class PassMonitor(Monitor):
    def __init__(self, name: str = "pass") -> None:
        super().__init__(name)
        self.init_called = False
        self.start_called = False
        self.stop_called = False

    async def initialize(self, ctx: MonitorContext) -> None:
        await super().initialize(ctx)
        self.init_called = True

    async def start(self) -> None:
        await super().start()
        self.start_called = True

    async def stop(self) -> None:
        await super().stop()
        self.stop_called = True


class FailInitMonitor(Monitor):
    async def initialize(self, _ctx: MonitorContext) -> None:
        raise RuntimeError("Init failure")

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


class FailStartMonitor(Monitor):
    async def initialize(self, ctx: MonitorContext) -> None:
        await super().initialize(ctx)

    async def start(self) -> None:
        raise RuntimeError("Start failure")

    async def stop(self) -> None:
        pass


class SlowMonitor(Monitor):
    def __init__(self, name: str = "slow", start_delay: float = 0.1) -> None:
        super().__init__(name)
        self._start_delay = start_delay

    async def initialize(self, ctx: MonitorContext) -> None:
        await super().initialize(ctx)

    async def start(self) -> None:
        await asyncio.sleep(self._start_delay)
        await super().start()

    async def stop(self) -> None:
        await super().stop()


class TestMonitorInterface:
    def test_monitor_creation(self) -> None:
        monitor = PassMonitor("test-monitor")
        assert monitor.name == "test-monitor"
        assert monitor.context is None

    @pytest.mark.asyncio
    async def test_monitor_initialize(self) -> None:
        monitor = PassMonitor()
        ctx = MonitorContext(name="test")
        await monitor.initialize(ctx)
        assert monitor.init_called
        assert monitor.context is not None

    @pytest.mark.asyncio
    async def test_monitor_start_stop(self) -> None:
        monitor = PassMonitor()
        await monitor.initialize(MonitorContext(name="test"))
        await monitor.start()
        assert monitor.start_called
        assert monitor.health().status == HealthState.HEALTHY
        await monitor.stop()
        assert monitor.stop_called
        assert monitor.health().status == HealthState.STOPPED

    @pytest.mark.asyncio
    async def test_monitor_health(self) -> None:
        monitor = PassMonitor()
        health = monitor.health()
        assert isinstance(health, HealthReport)
        assert health.status == HealthState.STOPPED

    def test_monitor_capabilities_default(self) -> None:
        caps = PassMonitor().capabilities()
        assert isinstance(caps, dict)


class TestMonitorRegistry:
    def test_register_and_lookup(self) -> None:
        reg = MonitorRegistry()
        m = PassMonitor("m1")
        reg.register(m)
        assert reg.lookup("m1") is m
        assert reg.count == 1

    def test_duplicate_raises(self) -> None:
        reg = MonitorRegistry()
        reg.register(PassMonitor("m1"))
        with pytest.raises(MonitorRegistrationError):
            reg.register(PassMonitor("m1"))

    def test_empty_name_raises(self) -> None:
        reg = MonitorRegistry()
        with pytest.raises(MonitorRegistrationError):
            reg.register(PassMonitor(""))

    def test_unregister(self) -> None:
        reg = MonitorRegistry()
        reg.register(PassMonitor("m1"))
        reg.unregister("m1")
        assert reg.count == 0

    def test_unregister_nonexistent_raises(self) -> None:
        reg = MonitorRegistry()
        with pytest.raises(MonitorNotFoundError):
            reg.unregister("x")

    def test_lookup_nonexistent_raises(self) -> None:
        reg = MonitorRegistry()
        with pytest.raises(MonitorNotFoundError):
            reg.lookup("x")

    def test_enable_disable(self) -> None:
        reg = MonitorRegistry()
        reg.register(PassMonitor("m1"))
        reg.register(PassMonitor("m2"))
        assert reg.enabled_count == 2
        reg.disable("m1")
        assert not reg.is_enabled("m1")
        assert reg.enabled_count == 1
        reg.enable("m1")
        assert reg.enabled_count == 2

    def test_list_enabled(self) -> None:
        reg = MonitorRegistry()
        m1 = PassMonitor("m1")
        m2 = PassMonitor("m2")
        reg.register(m1)
        reg.register(m2)
        reg.disable("m1")
        enabled = reg.list_enabled()
        assert len(enabled) == 1
        assert enabled[0].name == "m2"

    def test_list_disabled(self) -> None:
        reg = MonitorRegistry()
        reg.register(PassMonitor("m1"))
        reg.register(PassMonitor("m2"))
        reg.disable("m1")
        assert len(reg.list_disabled()) == 1

    def test_clear(self) -> None:
        reg = MonitorRegistry()
        reg.register(PassMonitor("m1"))
        reg.register(PassMonitor("m2"))
        reg.clear()
        assert reg.count == 0

    def test_names(self) -> None:
        reg = MonitorRegistry()
        reg.register(PassMonitor("a"))
        reg.register(PassMonitor("b"))
        assert reg.names == ["a", "b"]


class TestMonitorLifecycleEvents:
    def test_started_event(self) -> None:
        e = monitor_started("test")
        assert e.internal_type == "monitor.started"
        assert e.data["monitor"] == "test"

    def test_stopped_event(self) -> None:
        e = monitor_stopped("test")
        assert e.internal_type == "monitor.stopped"

    def test_failed_event(self) -> None:
        e = monitor_failed("test", "error")
        assert e.internal_type == "monitor.failed"

    def test_health_changed_event(self) -> None:
        e = monitor_health_changed("test", "HEALTHY", "DEGRADED")
        assert e.internal_type == "monitor.health_changed"


class TestMonitorManager:
    @pytest.mark.asyncio
    async def test_initialize_all(self) -> None:
        bus = EventBus()
        await bus.start()
        reg = MonitorRegistry()
        reg.register(PassMonitor("m1"))
        reg.register(PassMonitor("m2"))
        manager = MonitorManager(bus, reg)
        await manager.initialize_all()
        assert reg.lookup("m1").context is not None
        assert reg.lookup("m2").context is not None
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_start_all(self) -> None:
        bus = EventBus()
        await bus.start()
        reg = MonitorRegistry()
        m1 = PassMonitor("m1")
        m2 = PassMonitor("m2")
        reg.register(m1)
        reg.register(m2)
        manager = MonitorManager(bus, reg)
        await manager.initialize_all()
        await manager.start_all()
        assert m1.start_called
        assert m2.start_called
        assert manager.is_started
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_stop_all(self) -> None:
        bus = EventBus()
        await bus.start()
        reg = MonitorRegistry()
        m = PassMonitor("m1")
        reg.register(m)
        manager = MonitorManager(bus, reg)
        await manager.initialize_all()
        await manager.start_all()
        await manager.stop_all()
        assert m.stop_called
        assert not manager.is_started
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_fail_init_does_not_block(self) -> None:
        bus = EventBus()
        await bus.start()
        reg = MonitorRegistry()
        reg.register(PassMonitor("good"))
        reg.register(FailInitMonitor("bad"))
        reg.register(PassMonitor("also"))
        manager = MonitorManager(bus, reg)
        await manager.initialize_all()
        assert reg.is_enabled("good")
        assert not reg.is_enabled("bad")
        assert reg.is_enabled("also")
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_fail_start_does_not_block(self) -> None:
        bus = EventBus()
        await bus.start()
        reg = MonitorRegistry()
        m1 = PassMonitor("good")
        m2 = FailStartMonitor("bad")
        m3 = PassMonitor("also")
        reg.register(m1)
        reg.register(m2)
        reg.register(m3)
        manager = MonitorManager(bus, reg)
        await manager.initialize_all()
        await manager.start_all()
        assert m1.start_called
        assert m3.start_called
        assert not reg.is_enabled("bad")
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_health_report(self) -> None:
        bus = EventBus()
        await bus.start()
        reg = MonitorRegistry()
        reg.register(PassMonitor("healthy"))
        manager = MonitorManager(bus, reg)
        await manager.initialize_all()
        await manager.start_all()
        report = manager.health_report()
        assert "healthy" in report
        assert report["healthy"]["status"] == "HEALTHY"
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_metrics(self) -> None:
        bus = EventBus()
        await bus.start()
        reg = MonitorRegistry()
        reg.register(PassMonitor("m1"))
        reg.register(PassMonitor("m2"))
        manager = MonitorManager(bus, reg)
        await manager.initialize_all()
        await manager.start_all()
        snap = manager.metrics_snapshot()
        assert snap.registered_monitors == 2
        assert snap.enabled_monitors >= 0
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_start(self) -> None:
        bus = EventBus()
        await bus.start()
        reg = MonitorRegistry()
        s1 = SlowMonitor("s1", 0.2)
        s2 = SlowMonitor("s2", 0.2)
        reg.register(s1)
        reg.register(s2)
        manager = MonitorManager(bus, reg)
        await manager.initialize_all()
        start = time.monotonic()
        await manager.start_all()
        elapsed = time.monotonic() - start
        assert elapsed < 0.35, f"Concurrent start took {elapsed:.2f}s"
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_double_stop_safe(self) -> None:
        bus = EventBus()
        await bus.start()
        reg = MonitorRegistry()
        reg.register(PassMonitor("m1"))
        manager = MonitorManager(bus, reg)
        await manager.initialize_all()
        await manager.start_all()
        await manager.stop_all()
        await manager.stop_all()
        await bus.shutdown()


class TestMonitorContext:
    def test_context_creation(self) -> None:
        ctx = MonitorContext(name="test", settings={"key": "val"})
        assert ctx.name == "test"
        assert ctx.settings["key"] == "val"

    def test_context_defaults(self) -> None:
        ctx = MonitorContext()
        assert ctx.name == ""
        assert ctx.settings == {}
        assert ctx.metadata == {}


class TestMonitorBenchmarks:
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_ten_monitors_startup(self) -> None:
        bus = EventBus()
        await bus.start()
        reg = MonitorRegistry()
        for i in range(10):
            reg.register(PassMonitor(f"m{i}"))
        manager = MonitorManager(bus, reg)
        await manager.initialize_all()
        start = time.monotonic()
        await manager.start_all()
        elapsed = time.monotonic() - start
        print(f"\n  10-monitor startup: {elapsed * 1000:.1f}ms")
        assert elapsed < 2.0
        await bus.shutdown()

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_fifty_monitors_registry(self) -> None:
        reg = MonitorRegistry()
        for i in range(50):
            reg.register(PassMonitor(f"m{i}"))
        assert reg.count == 50
        assert reg.enabled_count == 50
