"""
Firewall backend registry — manages backend registration and lookup.
"""

from __future__ import annotations

from security_agent.firewall.backend import FirewallBackend
from security_agent.firewall.exceptions import (
    BackendRegistrationError,
    UnsupportedBackendError,
)


class BackendRegistry:
    """Registry of firewall backends."""

    def __init__(self) -> None:
        self._backends: dict[str, FirewallBackend] = {}
        self._order: list[str] = []

    def register(self, backend: FirewallBackend) -> None:
        """Register a firewall backend."""
        if not backend.name:
            raise BackendRegistrationError("Backend name cannot be empty")
        if backend.name in self._backends:
            raise BackendRegistrationError(
                f"Backend '{backend.name}' is already registered"
            )
        self._backends[backend.name] = backend
        self._order.append(backend.name)

    def unregister(self, name: str) -> None:
        if name not in self._backends:
            raise UnsupportedBackendError(f"Backend '{name}' not found")
        del self._backends[name]
        self._order.remove(name)

    def get(self, name: str) -> FirewallBackend:
        if name not in self._backends:
            raise UnsupportedBackendError(f"Backend '{name}' not found")
        return self._backends[name]

    def list_all(self) -> list[FirewallBackend]:
        return [self._backends[name] for name in self._order]

    def find_by_capability(self, capability: str) -> list[FirewallBackend]:
        """Find backends that support a specific capability."""
        results: list[FirewallBackend] = []
        for backend in self.list_all():
            caps = backend.capabilities()
            if getattr(caps, capability, False):
                results.append(backend)
        return results

    def has_backend(self, name: str) -> bool:
        return name in self._backends

    @property
    def count(self) -> int:
        return len(self._backends)

    @property
    def names(self) -> list[str]:
        return list(self._order)

    def clear(self) -> None:
        self._backends.clear()
        self._order.clear()
