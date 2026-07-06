"""
Comprehensive tests for the Firewall Abstraction Layer.
"""

from __future__ import annotations

import time

import pytest

from security_agent.ban.models import BanAction, BanDecision
from security_agent.firewall import (
    BackendCapabilities,
    BackendRegistry,
    FirewallBackend,
    FirewallManager,
    FirewallOperation,
    OperationType,
)
from security_agent.firewall.exceptions import (
    BackendRegistrationError,
)
from security_agent.firewall.operation import create_operation


class MockFirewallBackend(FirewallBackend):
    """Mock backend for testing."""

    def __init__(
        self, name: str = "mock", capabilities: BackendCapabilities | None = None
    ) -> None:
        super().__init__(name)
        self._caps = capabilities or BackendCapabilities(ipv4=True, temporary_bans=True)
        self.applied: list[FirewallOperation] = []
        self.removed: list[FirewallOperation] = []
        self.initialized = False
        self.shut_down = False

    async def initialize(self) -> None:
        self.initialized = True

    async def apply(self, operation: FirewallOperation) -> bool:
        self.applied.append(operation)
        return True

    async def remove(self, operation: FirewallOperation) -> bool:
        self.removed.append(operation)
        return True

    async def synchronize(self, operations: list[FirewallOperation]) -> int:
        self.applied.extend(operations)
        return len(operations)

    def capabilities(self) -> BackendCapabilities:
        return self._caps

    async def shutdown(self) -> None:
        self.shut_down = True


class TestFirewallOperation:
    def test_creation(self) -> None:
        op = FirewallOperation(
            entity="1.2.3.4", operation_type=OperationType.BAN, duration=3600
        )
        assert op.entity == "1.2.3.4"
        assert op.operation_type == OperationType.BAN
        assert op.duration == 3600

    def test_frozen(self) -> None:
        op = FirewallOperation()
        with pytest.raises(AttributeError):
            op.entity = "x"  # type: ignore[misc]


class TestOperationFactory:
    def test_ban_decision_to_operation(self) -> None:
        d = BanDecision(
            entity="1.2.3.4",
            entity_type="ipv4",
            action=BanAction.TEMPORARY_BAN,
            ban_duration=3600,
            threat_score=70,
            confidence=80,
            correlation_id="corr-001",
        )
        op = create_operation(d)
        assert op is not None
        assert op.operation_type == OperationType.BAN
        assert op.entity == "1.2.3.4"

    def test_warning_no_ban(self) -> None:
        d = BanDecision(action=BanAction.WARNING, threat_score=10, confidence=50)
        op = create_operation(d)
        assert op is not None
        assert op.operation_type == OperationType.REFRESH

    def test_whitelist_skip(self) -> None:
        d = BanDecision(action=BanAction.WHITELIST_SKIP, threat_score=90, confidence=95)
        op = create_operation(d)
        assert op is None

    def test_no_action(self) -> None:
        d = BanDecision(action=BanAction.NO_ACTION, threat_score=0, confidence=0)
        op = create_operation(d)
        assert op is None

    def test_permanent_ban(self) -> None:
        d = BanDecision(
            action=BanAction.PERMANENT_BAN,
            ban_duration=0,
            threat_score=95,
            confidence=95,
        )
        op = create_operation(d)
        assert op is not None
        assert op.duration == 0


class TestBackendCapabilities:
    def test_defaults(self) -> None:
        c = BackendCapabilities()
        assert not c.ipv4
        assert not c.ipv6

    def test_custom(self) -> None:
        c = BackendCapabilities(ipv4=True, ipv6=True, temporary_bans=True)
        assert c.ipv4
        assert c.ipv6
        assert c.temporary_bans
        assert not c.permanent_bans


class TestBackendRegistry:
    def test_register(self) -> None:
        reg = BackendRegistry()
        b = MockFirewallBackend("test")
        reg.register(b)
        assert reg.count == 1
        assert reg.get("test") is b

    def test_duplicate_raises(self) -> None:
        reg = BackendRegistry()
        reg.register(MockFirewallBackend("b1"))
        with pytest.raises(BackendRegistrationError):
            reg.register(MockFirewallBackend("b1"))

    def test_empty_name_raises(self) -> None:
        reg = BackendRegistry()
        with pytest.raises(BackendRegistrationError):
            reg.register(MockFirewallBackend(""))

    def test_find_by_capability(self) -> None:
        reg = BackendRegistry()
        reg.register(MockFirewallBackend("ipv4_only", BackendCapabilities(ipv4=True)))
        reg.register(
            MockFirewallBackend("full", BackendCapabilities(ipv4=True, ipv6=True))
        )
        results = reg.find_by_capability("ipv6")
        assert len(results) == 1
        assert results[0].name == "full"


class TestFirewallManager:
    @pytest.mark.asyncio
    async def test_register_and_init(self) -> None:
        mgr = FirewallManager()
        b = MockFirewallBackend("test")
        mgr.register_backend(b)
        await mgr.initialize_all()
        assert b.initialized
        assert mgr.is_initialized

    @pytest.mark.asyncio
    async def test_process_decision(self) -> None:
        mgr = FirewallManager()
        mgr.register_backend(MockFirewallBackend("test"))
        await mgr.initialize_all()

        d = BanDecision(
            action=BanAction.TEMPORARY_BAN,
            ban_duration=3600,
            entity="1.2.3.4",
            entity_type="ipv4",
            threat_score=70,
            confidence=80,
            correlation_id="c1",
        )
        op = await mgr.process_decision(d)
        assert op is not None
        assert op.entity == "1.2.3.4"

    @pytest.mark.asyncio
    async def test_whitelist_skips_firewall(self) -> None:
        mgr = FirewallManager()
        mgr.register_backend(MockFirewallBackend("test"))
        await mgr.initialize_all()

        d = BanDecision(action=BanAction.WHITELIST_SKIP, threat_score=90, confidence=95)
        op = await mgr.process_decision(d)
        assert op is None

    @pytest.mark.asyncio
    async def test_shutdown(self) -> None:
        mgr = FirewallManager()
        b = MockFirewallBackend("test")
        mgr.register_backend(b)
        await mgr.initialize_all()
        await mgr.shutdown_all()
        assert b.shut_down

    @pytest.mark.asyncio
    async def test_metrics(self) -> None:
        mgr = FirewallManager()
        mgr.register_backend(MockFirewallBackend("test"))
        await mgr.initialize_all()

        d = BanDecision(
            action=BanAction.TEMPORARY_BAN,
            ban_duration=3600,
            entity="1.2.3.4",
            entity_type="ipv4",
            threat_score=70,
            confidence=80,
            correlation_id="c1",
        )
        await mgr.process_decision(d)
        snap = mgr.metrics_snapshot()
        assert snap.operations_created >= 1


class TestBenchmarks:
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_operation_throughput(self) -> None:
        mgr = FirewallManager()
        mgr.register_backend(MockFirewallBackend("test"))
        await mgr.initialize_all()
        n = 5000
        t = time.monotonic()
        for i in range(n):
            d = BanDecision(
                action=BanAction.TEMPORARY_BAN,
                ban_duration=3600,
                entity=f"10.0.0.{i % 256}",
                entity_type="ipv4",
                threat_score=70,
                confidence=80,
                correlation_id=f"c{i}",
            )
            await mgr.process_decision(d)
        elapsed = time.monotonic() - t
        print(f"\n  Throughput: {n / elapsed:.0f} ops/s ({n} in {elapsed:.3f}s)")
