"""iptables FirewallBackend — concrete FirewallBackend implementation."""

from __future__ import annotations

import logging

from security_agent.firewall.backend import FirewallBackend
from security_agent.firewall.executor import IptablesExecutor, validate_ip
from security_agent.firewall.metrics import FirewallMetricsCollector
from security_agent.firewall.models import (
    BackendCapabilities,
    FirewallOperation,
    OperationType,
)
from security_agent.firewall.parser import count_rules_for_chain, extract_ips_from_rules
from security_agent.firewall.state import FirewallState

logger = logging.getLogger("firewall.iptables")


class IptablesBackend(FirewallBackend):  # type: ignore[misc]
    """Concrete iptables backend using dedicated AI_SECURITY_AGENT chain."""

    def __init__(self, name: str = "iptables") -> None:
        super().__init__(name)
        self._executor = IptablesExecutor()
        self._state = FirewallState()
        self._metrics = FirewallMetricsCollector()
        self._initialized = False

    async def initialize(self) -> None:
        chain_ok = await self._executor.create_chain()
        ref_ok = await self._executor.ensure_chain_referenced()
        self._initialized = chain_ok and ref_ok
        if self._initialized:
            logger.info("iptables backend initialized")

    async def apply(self, operation: FirewallOperation) -> bool:
        if operation.operation_type == OperationType.BAN:
            validate_ip(operation.entity)
            ok = await self._executor.add_rule(
                operation.entity, comment=operation.reason[:256]
            )
            if ok:
                self._state.add_desired(
                    operation.entity, operation.entity_type, reason=operation.reason
                )
                self._metrics.operation_completed()
            else:
                self._metrics.operation_failed()
            return bool(ok)

        if operation.operation_type == OperationType.REFRESH:
            exists = await self._executor.rule_exists(operation.entity)
            if not exists:
                return bool(await self._executor.add_rule(operation.entity))
            self._metrics.operation_completed()
            return True

        if operation.operation_type == OperationType.VERIFY:
            exists = await self._executor.rule_exists(operation.entity)
            self._metrics.operation_completed()
            return bool(exists)

        self._metrics.operation_failed()
        return False

    async def remove(self, operation: FirewallOperation) -> bool:
        if operation.operation_type in (OperationType.UNBAN, OperationType.BAN):
            ok = await self._executor.remove_rule(operation.entity)
            if ok:
                self._state.remove_desired(operation.entity)
                self._metrics.operation_completed()
            else:
                self._metrics.operation_failed()
            return bool(ok)
        self._metrics.operation_failed()
        return False

    async def synchronize(self, operations: list[FirewallOperation]) -> int:
        self._metrics.sync_requested()
        desired_ips = set(d["entity"] for d in self._state.get_desired())
        actual_rules = await self._executor.list_rules()
        actual_ips = extract_ips_from_rules(actual_rules)
        to_add, to_remove = self._state.compute_sync_actions(desired_ips, actual_ips)
        count = 0
        for ip in to_add:
            if await self._executor.add_rule(ip):
                count += 1
        if to_add or to_remove:
            logger.info("Sync: %d added, %d removed", len(to_add), len(to_remove))
        return int(count)

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            ipv4=True,
            ipv6=False,
            cidr=False,
            ipset=False,
            nftables_sets=False,
            temporary_bans=True,
            permanent_bans=True,
            synchronization=True,
            batch_operations=False,
            name=self.name,
        )

    async def shutdown(self) -> None:
        self._initialized = False

    async def get_rule_count(self) -> int:
        try:
            code, output = await self._executor.run(["-S", "AI_SECURITY_AGENT"])
            if code == 0:
                return int(count_rules_for_chain(output))
        except Exception:
            pass
        return 0
