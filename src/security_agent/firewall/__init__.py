"""Firewall Abstraction Layer — defines what firewall operations should happen."""

from security_agent.firewall.backend import FirewallBackend
from security_agent.firewall.manager import FirewallManager
from security_agent.firewall.models import (
    BackendCapabilities,
    FirewallOperation,
    OperationType,
)
from security_agent.firewall.registry import BackendRegistry

__all__ = [
    "BackendCapabilities",
    "BackendRegistry",
    "FirewallBackend",
    "FirewallManager",
    "FirewallOperation",
    "OperationType",
]
