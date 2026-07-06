"""
Command models — immutable RemoteCommand, lifecycle states, command type registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum, auto
from typing import Any
from uuid import uuid4


class CommandState(StrEnum):
    """All possible command lifecycle states."""

    CREATED = auto()
    QUEUED = auto()
    AUTHORIZED = auto()
    READY = auto()
    DELIVERED = auto()
    ACKNOWLEDGED = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    CANCELLED = auto()
    EXPIRED = auto()


class CommandPriority(StrEnum):
    """Command priority levels."""

    IMMEDIATE = auto()
    HIGH = auto()
    NORMAL = auto()
    LOW = auto()


class CommandType(StrEnum):
    """All supported command types — adding requires registration."""

    RELOAD_CONFIGURATION = auto()
    RELOAD_RULES = auto()
    ROTATE_CERTIFICATE = auto()
    REVOKE_CERTIFICATE = auto()
    SYNCHRONIZE_FIREWALL = auto()
    VERIFY_FIREWALL = auto()
    COLLECT_DIAGNOSTICS = auto()
    BENCHMARK = auto()
    RESTART_AGENT = auto()
    GRACEFUL_SHUTDOWN = auto()
    MAINTENANCE_ENABLE = auto()
    MAINTENANCE_DISABLE = auto()


COMMAND_PARAMETER_SCHEMAS: dict[str, dict[str, Any]] = {
    "reload_configuration": {
        "description": "Reload agent configuration",
        "parameters": {
            "config_version": {
                "type": "string",
                "default": "",
                "description": "Target config version",
            },
        },
    },
    "reload_rules": {
        "description": "Reload detection rules",
        "parameters": {
            "rule_version": {"type": "string", "default": "", "description": "Target rule version"},
        },
    },
    "rotate_certificate": {
        "description": "Rotate machine certificate",
        "parameters": {},
    },
    "revoke_certificate": {
        "description": "Revoke current certificate",
        "parameters": {
            "reason": {"type": "string", "default": "", "description": "Revocation reason"},
        },
    },
    "synchronize_firewall": {
        "description": "Synchronize firewall rules",
        "parameters": {},
    },
    "verify_firewall": {
        "description": "Verify firewall configuration",
        "parameters": {},
    },
    "collect_diagnostics": {
        "description": "Collect diagnostic information",
        "parameters": {
            "include_logs": {"type": "bool", "default": True, "description": "Include log files"},
            "include_config": {
                "type": "bool",
                "default": True,
                "description": "Include configuration",
            },
        },
    },
    "benchmark": {
        "description": "Run performance benchmarks",
        "parameters": {
            "duration_seconds": {"type": "int", "default": 60, "description": "Benchmark duration"},
        },
    },
    "restart_agent": {
        "description": "Restart the AI Security Agent",
        "parameters": {
            "force": {"type": "bool", "default": False, "description": "Force restart"},
        },
    },
    "graceful_shutdown": {
        "description": "Gracefully shut down the agent",
        "parameters": {
            "reason": {"type": "string", "default": "", "description": "Shutdown reason"},
        },
    },
    "maintenance_enable": {
        "description": "Enable maintenance mode",
        "parameters": {
            "duration_minutes": {
                "type": "int",
                "default": 60,
                "description": "Maintenance duration",
            },
        },
    },
    "maintenance_disable": {
        "description": "Disable maintenance mode",
        "parameters": {},
    },
}

ALLOWED_PARAMETER_TYPES = {"string", "bool", "int", "float"}


@dataclass(frozen=True)
class RemoteCommand:
    """Immutable remote command.

    Never modified after creation. State changes create new lifecycle records.
    """

    command_id: str = ""
    correlation_id: str = ""
    machine_id: str = ""
    command_type: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    priority: CommandPriority = CommandPriority.NORMAL
    state: CommandState = CommandState.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    expires_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC) + timedelta(hours=24))
    requested_by: str = "system"
    policy_version: str = ""
    feature_flags: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        machine_id: str,
        command_type: str,
        parameters: dict[str, Any] | None = None,
        priority: CommandPriority = CommandPriority.NORMAL,
        correlation_id: str | None = None,
        requested_by: str = "system",
        ttl_hours: int = 24,
    ) -> RemoteCommand:
        return cls(
            command_id=uuid4().hex[:16],
            correlation_id=correlation_id or uuid4().hex[:16],
            machine_id=machine_id,
            command_type=command_type,
            parameters=parameters or {},
            priority=priority,
            state=CommandState.CREATED,
            expires_at=datetime.now(tz=UTC) + timedelta(hours=ttl_hours),
            requested_by=requested_by,
        )

    @property
    def is_expired(self) -> bool:
        return datetime.now(tz=UTC) > self.expires_at


@dataclass
class CommandLifecycleRecord:
    """A single lifecycle transition record (append-only)."""

    command_id: str = ""
    from_state: CommandState = CommandState.CREATED
    to_state: CommandState = CommandState.CREATED
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    triggered_by: str = "system"
    reason: str = ""
