"""
Monitor Registry — manages monitor registration, lookup, and enable/disable.

The registry validates names, prevents duplicates, and enables querying
of registered monitors.
"""

from __future__ import annotations

from security_agent.monitors.base import Monitor
from security_agent.monitors.exceptions import (
    MonitorNotFoundError,
    MonitorRegistrationError,
)


class MonitorRegistry:
    """Registry of monitor instances.

    Supports:
    - Registering monitors
    - Unregistering monitors
    - Looking up monitors by name
    - Enabling/disabling monitors
    - Listing all registered monitors
    - Listing enabled monitors
    """

    def __init__(self) -> None:
        self._monitors: dict[str, Monitor] = {}
        self._enabled: dict[str, bool] = {}

    def register(self, monitor: Monitor) -> None:
        """Register a monitor.

        Raises MonitorRegistrationError if:
        - A monitor with the same name already exists.
        - The monitor name is empty.
        """
        if not monitor.name:
            raise MonitorRegistrationError("Monitor name cannot be empty")
        if monitor.name in self._monitors:
            raise MonitorRegistrationError(
                f"Monitor '{monitor.name}' is already registered"
            )
        self._monitors[monitor.name] = monitor
        self._enabled[monitor.name] = True

    def unregister(self, name: str) -> None:
        """Remove a monitor from the registry."""
        if name not in self._monitors:
            raise MonitorNotFoundError(f"Monitor '{name}' not found")
        del self._monitors[name]
        del self._enabled[name]

    def lookup(self, name: str) -> Monitor:
        """Find a monitor by name."""
        if name not in self._monitors:
            raise MonitorNotFoundError(f"Monitor '{name}' not found")
        return self._monitors[name]

    def enable(self, name: str) -> None:
        """Enable a previously disabled monitor."""
        if name not in self._monitors:
            raise MonitorNotFoundError(f"Monitor '{name}' not found")
        self._enabled[name] = True

    def disable(self, name: str) -> None:
        """Disable a monitor (skip during start)."""
        if name not in self._monitors:
            raise MonitorNotFoundError(f"Monitor '{name}' not found")
        self._enabled[name] = False

    def is_enabled(self, name: str) -> bool:
        """Check if a monitor is enabled."""
        return self._enabled.get(name, False)

    def list_all(self) -> list[Monitor]:
        """Return all registered monitors."""
        return list(self._monitors.values())

    def list_enabled(self) -> list[Monitor]:
        """Return enabled monitors only."""
        return [m for m in self._monitors.values() if self._enabled.get(m.name, False)]

    def list_disabled(self) -> list[Monitor]:
        """Return disabled monitors only."""
        return [
            m for m in self._monitors.values() if not self._enabled.get(m.name, False)
        ]

    @property
    def count(self) -> int:
        """Total registered monitors."""
        return len(self._monitors)

    @property
    def enabled_count(self) -> int:
        """Number of enabled monitors."""
        return sum(1 for v in self._enabled.values() if v)

    @property
    def names(self) -> list[str]:
        """Names of all registered monitors."""
        return list(self._monitors.keys())

    def clear(self) -> None:
        """Remove all monitors."""
        self._monitors.clear()
        self._enabled.clear()
