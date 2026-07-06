"""
Abstract FirewallBackend interface.

Concrete backends (iptables, nftables, ipset, etc.) implement this interface.
The FirewallManager interacts only through this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from security_agent.firewall.models import BackendCapabilities, FirewallOperation


class FirewallBackend(ABC):
    """Abstract interface for firewall backends.

    Implementations:
        - iptables.py
        - nftables.py
        - ipset.py
        - fail2ban.py
    """

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    async def initialize(self) -> None:
        """Prepare the backend for operations.

        Called once when the backend is registered.
        Should validate that required tools are available.
        """

    @abstractmethod
    async def apply(self, operation: FirewallOperation) -> bool:
        """Apply a firewall operation (ban, refresh, etc.).

        Returns True if successful.
        """

    @abstractmethod
    async def remove(self, operation: FirewallOperation) -> bool:
        """Remove a previously applied operation (unban).

        Returns True if successful.
        """

    @abstractmethod
    async def synchronize(self, operations: list[FirewallOperation]) -> int:
        """Synchronize firewall state with desired state.

        Returns the number of operations applied.
        """

    @abstractmethod
    def capabilities(self) -> BackendCapabilities:
        """Declare what operations this backend supports."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Release backend resources."""
