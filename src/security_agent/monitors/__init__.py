"""Monitor Framework — unified event collection from multiple sources."""

from security_agent.monitors.base import HealthReport, HealthState, Monitor
from security_agent.monitors.context import MonitorContext
from security_agent.monitors.exceptions import (
    MonitorError,
    MonitorNotFoundError,
    MonitorNotRunningError,
    MonitorRegistrationError,
    MonitorShutdownError,
    MonitorStartupError,
    MonitorTimeoutError,
)
from security_agent.monitors.manager import MonitorManager
from security_agent.monitors.metrics import (
    MonitorMetricsCollector,
    MonitorMetricsSnapshot,
)
from security_agent.monitors.registry import MonitorRegistry

__all__ = [
    "HealthReport",
    "HealthState",
    "Monitor",
    "MonitorContext",
    "MonitorError",
    "MonitorManager",
    "MonitorMetricsCollector",
    "MonitorMetricsSnapshot",
    "MonitorNotFoundError",
    "MonitorNotRunningError",
    "MonitorRegistrationError",
    "MonitorRegistry",
    "MonitorShutdownError",
    "MonitorStartupError",
    "MonitorTimeoutError",
]
