"""
FirewallManager — manages backend lifecycle, operation dispatch, and capability validation.

No concrete backend code here. Only abstraction.
"""

from __future__ import annotations

import logging
from typing import Any

from security_agent.ban.models import BanDecision
from security_agent.firewall.backend import FirewallBackend
from security_agent.firewall.exceptions import (
    BackendUnavailableError,
)
from security_agent.firewall.metrics import (
    FirewallMetricsCollector,
    FirewallMetricsSnapshot,
)
from security_agent.firewall.models import FirewallOperation
from security_agent.firewall.operation import create_operation
from security_agent.firewall.registry import BackendRegistry

logger = logging.getLogger("firewall.manager")


class FirewallManager:
    """Manages firewall backends and dispatches operations.

    No concrete backend code. Only abstraction and orchestration.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._registry = BackendRegistry()
        self._config = config or {}
        self._metrics = FirewallMetricsCollector()
        self._initialized = False

    async def initialize_all(self) -> None:
        """Initialize all registered backends."""
        for backend in self._registry.list_all():
            try:
                await backend.initialize()
                logger.info("Backend initialized", extra={"backend": backend.name})
            except Exception as e:
                logger.error(
                    "Backend init failed",
                    extra={
                        "backend": backend.name,
                        "error": str(e),
                    },
                )
        self._initialized = True

    async def shutdown_all(self) -> None:
        """Shut down all registered backends."""
        for backend in self._registry.list_all():
            try:
                await backend.shutdown()
            except Exception as e:
                logger.error(
                    "Backend shutdown error",
                    extra={
                        "backend": backend.name,
                        "error": str(e),
                    },
                )

    async def process_decision(self, decision: BanDecision) -> FirewallOperation | None:
        """Process a BanDecision and dispatch to appropriate backends.

        Returns the created FirewallOperation or None if no action needed.
        """
        operation = create_operation(decision)
        if operation is None:
            return None

        self._metrics.operation_created()

        # Find backends that can handle this operation
        backends = self._find_backends(operation)
        if not backends:
            raise BackendUnavailableError(
                f"No backend available for operation {operation.operation_type}"
            )

        for backend in backends:
            try:
                success = await backend.apply(operation)
                if success:
                    self._metrics.operation_completed()
                else:
                    self._metrics.operation_failed()
                    logger.warning(
                        "Backend apply failed",
                        extra={
                            "backend": backend.name,
                            "op": operation.operation_id,
                        },
                    )
            except Exception as e:
                self._metrics.backend_failure()
                logger.error(
                    "Backend error",
                    extra={
                        "backend": backend.name,
                        "error": str(e),
                    },
                )

        return operation

    async def remove_operation(self, operation: FirewallOperation) -> bool:
        """Remove a previously applied operation (unban)."""
        backends = self._find_backends(operation)
        success = True
        for backend in backends:
            try:
                if not await backend.remove(operation):
                    success = False
            except Exception:
                self._metrics.backend_failure()
                success = False
        return success

    async def synchronize(self, operations: list[FirewallOperation]) -> int:
        """Synchronize firewall state across all backends.

        Returns total operations synchronized.
        """
        self._metrics.sync_requested()
        total = 0
        for backend in self._registry.list_all():
            try:
                count = await backend.synchronize(operations)
                total += count
            except Exception as e:
                self._metrics.backend_failure()
                logger.error(
                    "Sync failed",
                    extra={
                        "backend": backend.name,
                        "error": str(e),
                    },
                )
        return total

    def register_backend(self, backend: FirewallBackend) -> None:
        """Register a firewall backend."""
        self._registry.register(backend)

    def get_backend(self, name: str) -> FirewallBackend:
        return self._registry.get(name)

    def find_backends_by_capability(self, capability: str) -> list[FirewallBackend]:
        return list(self._registry.find_by_capability(capability))

    def _find_backends(self, operation: FirewallOperation) -> list[FirewallBackend]:
        """Find backends suitable for an operation."""
        if operation.backend_hint:
            try:
                return [self._registry.get(operation.backend_hint)]
            except Exception:
                pass
        return list(self._registry.list_all())

    def metrics_snapshot(self) -> FirewallMetricsSnapshot:
        return self._metrics.snapshot(
            registered=self._registry.count,
        )

    @property
    def is_initialized(self) -> bool:
        return self._initialized
