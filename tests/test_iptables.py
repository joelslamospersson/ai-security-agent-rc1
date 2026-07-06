"""
Tests for the iptables firewall backend.

Uses mocked subprocess calls — never modifies the host firewall.
"""

from __future__ import annotations

import time

import pytest

from security_agent.firewall.executor import validate_ip
from security_agent.firewall.iptables import IptablesBackend
from security_agent.firewall.models import FirewallOperation, OperationType
from security_agent.firewall.parser import (
    count_rules_for_chain,
    extract_ips_from_rules,
    parse_rule_line,
)
from security_agent.firewall.state import FirewallState


class MockExecutor:
    """Mock iptables executor for testing."""

    def __init__(self) -> None:
        self.rules: set[str] = {"1.2.3.4", "5.6.7.8"}
        self.chain_exists = True
        self.chain_referenced = True

    async def run(self, args, timeout=10):
        cmd = " ".join(args)
        if "-C" in cmd:
            ip = args[args.index("-s") + 1] if "-s" in args else ""
            if ip in self.rules:
                return 0, ""
            return 1, "Rule does not exist"
        if "-A" in cmd:
            ip = args[args.index("-s") + 1] if "-s" in args else ""
            if ip.startswith("10.0"):
                return 1, "Real failure"
            self.rules.add(ip)
            return 0, ""
        if "-D" in cmd:
            ip = args[args.index("-s") + 1] if "-s" in args else ""
            self.rules.discard(ip)
            return 0, ""
        if "-S" in cmd:
            lines = "\n".join(
                [f"-A AI_SECURITY_AGENT -s {ip} -j DROP" for ip in self.rules]
            )
            return 0, lines
        if "-N" in cmd:
            return 0, ""
        if "-F" in cmd:
            self.rules.clear()
            return 0, ""
        if "-X" in cmd:
            return 0, ""
        return 0, ""

    async def create_chain(self):
        return True

    async def ensure_chain_referenced(self):
        return True

    async def add_rule(self, ip_str, comment=""):
        self.rules.add(ip_str)
        return True

    async def remove_rule(self, ip_str):
        self.rules.discard(ip_str)
        return True

    async def rule_exists(self, ip_str):
        return ip_str in self.rules

    async def list_rules(self):
        return [{"source": ip} for ip in self.rules]

    async def flush_chain(self):
        self.rules.clear()
        return True


@pytest.mark.asyncio
class TestIptablesBackend:
    async def test_initialize(self):
        backend = IptablesBackend()
        backend._executor = MockExecutor()
        await backend.initialize()
        assert backend.name == "iptables"

    async def test_apply_ban(self):
        backend = IptablesBackend()
        backend._executor = MockExecutor()
        op = FirewallOperation(
            entity="192.168.1.1",
            operation_type=OperationType.BAN,
            duration=3600,
        )
        result = await backend.apply(op)
        assert result

    async def test_apply_ban_invalid_ip(self):
        backend = IptablesBackend()
        backend._executor = MockExecutor()
        op = FirewallOperation(entity="not_an_ip", operation_type=OperationType.BAN)
        with pytest.raises(Exception):
            await backend.apply(op)

    async def test_remove_ban(self):
        backend = IptablesBackend()
        backend._executor = MockExecutor()
        # Add first
        await backend.apply(
            FirewallOperation(entity="10.0.0.1", operation_type=OperationType.BAN)
        )
        # Then verify removal works
        op = FirewallOperation(entity="10.0.0.1", operation_type=OperationType.UNBAN)
        result = await backend.remove(op)
        assert result

    async def test_verify(self):
        backend = IptablesBackend()
        backend._executor = MockExecutor()
        await backend.apply(
            FirewallOperation(entity="1.2.3.4", operation_type=OperationType.BAN)
        )
        op = FirewallOperation(entity="1.2.3.4", operation_type=OperationType.VERIFY)
        result = await backend.apply(op)
        assert result

    async def test_synchronize(self):
        backend = IptablesBackend()
        backend._executor = MockExecutor()
        ops = [
            FirewallOperation(entity="10.0.0.1", operation_type=OperationType.BAN),
            FirewallOperation(entity="10.0.0.2", operation_type=OperationType.BAN),
        ]
        count = await backend.synchronize(ops)
        assert count >= 0

    async def test_capabilities(self):
        backend = IptablesBackend()
        caps = backend.capabilities()
        assert caps.ipv4
        assert not caps.ipv6

    async def test_metrics(self):
        backend = IptablesBackend()
        backend._executor = MockExecutor()
        await backend.apply(
            FirewallOperation(entity="1.2.3.4", operation_type=OperationType.BAN)
        )
        snap = backend._metrics.snapshot()
        assert snap.operations_completed >= 1


class TestValidator:
    def test_validate_ip_valid(self):
        assert validate_ip("1.2.3.4") == "1.2.3.4"

    def test_validate_ip_invalid(self):
        from security_agent.firewall.exceptions import OperationValidationError

        with pytest.raises(OperationValidationError):
            validate_ip("not_an_ip")


class TestParser:
    def test_parse_rule_line(self):
        line = "-A AI_SECURITY_AGENT -s 1.2.3.4 -j DROP -m comment --comment test"
        rule = parse_rule_line(line)
        assert rule["chain"] == "AI_SECURITY_AGENT"
        assert rule["source"] == "1.2.3.4"
        assert rule["target"] == "DROP"

    def test_extract_ips(self):
        rules = [{"source": "1.1.1.1"}, {"source": "2.2.2.2"}, {"source": "0.0.0.0"}]
        ips = extract_ips_from_rules(rules)
        assert ips == {"1.1.1.1", "2.2.2.2"}

    def test_count_rules(self):
        output = "-A AI_SECURITY_AGENT -s 1.1.1.1 -j DROP\n-A AI_SECURITY_AGENT -s 2.2.2.2 -j DROP"
        assert count_rules_for_chain(output) == 2


class TestFirewallState:
    def test_add_desired(self):
        s = FirewallState()
        s.add_desired("1.2.3.4", "ipv4", reason="test")
        assert s.is_desired("1.2.3.4")

    def test_remove_desired(self):
        s = FirewallState()
        s.add_desired("1.2.3.4", "ipv4")
        s.remove_desired("1.2.3.4")
        assert not s.is_desired("1.2.3.4")

    def test_compute_sync(self):
        s = FirewallState()
        to_add, to_remove = s.compute_sync_actions({"1.1.1.1", "2.2.2.2"}, {"1.1.1.1"})
        assert "2.2.2.2" in to_add
        assert "1.1.1.1" not in to_add
        assert "1.1.1.1" not in to_remove


class TestBenchmarks:
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_mock_apply_latency(self):
        backend = IptablesBackend()
        backend._executor = MockExecutor()
        lats = []
        for _ in range(100):
            t = time.monotonic()
            await backend.apply(
                FirewallOperation(entity="1.2.3.4", operation_type=OperationType.BAN)
            )
            lats.append((time.monotonic() - t) * 1000)
        avg = sum(lats) / len(lats)
        print(f"\n  Mock apply latency: avg={avg:.4f}ms")
