"""
Logging models — log entries, report types, and directory structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from pathlib import Path
from typing import Any


class LogCategory(StrEnum):
    """Log categories mapping to directory structure."""

    SECURITY = auto()
    AUDIT = auto()
    FIREWALL = auto()
    HEARTBEAT = auto()
    NOTIFICATIONS = auto()
    COMMANDS = auto()
    MANAGEMENT = auto()
    PERFORMANCE = auto()
    DEBUG = auto()


class ReportPeriod(StrEnum):
    """Report generation periods."""

    DAILY = auto()
    WEEKLY = auto()
    MONTHLY = auto()


@dataclass
class LogEntry:
    """A single structured log entry."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    category: LogCategory = LogCategory.MANAGEMENT
    severity: str = "INFO"
    machine_id: str = ""
    correlation_id: str = ""
    event_type: str = ""
    description: str = ""
    source: str = ""
    threat_score: float = 0.0
    confidence: float = 0.0
    policy: str = ""
    action: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IncidentReport:
    """Report for a completed incident."""

    incident_id: str = ""
    correlation_id: str = ""
    start_time: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    end_time: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    duration_seconds: float = 0.0
    source: str = ""
    attack_type: str = ""
    detection_chain: list[str] = field(default_factory=list)
    threat_score: float = 0.0
    confidence: float = 0.0
    policy: str = ""
    firewall_actions: list[str] = field(default_factory=list)
    notifications_sent: list[str] = field(default_factory=list)
    final_resolution: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass
class DailyReport:
    """Daily summary report."""

    date: str = ""
    total_detections: int = 0
    critical_detections: int = 0
    commands_executed: int = 0
    machines_online: int = 0
    machines_offline: int = 0
    firewall_actions: int = 0
    top_attack_types: list[tuple[str, int]] = field(default_factory=list)
    top_offending_ips: list[str] = field(default_factory=list)
    average_response_time_ms: float = 0.0


LOG_DIRECTORIES: dict[LogCategory, str] = {
    LogCategory.SECURITY: "security",
    LogCategory.AUDIT: "audit",
    LogCategory.FIREWALL: "firewall",
    LogCategory.HEARTBEAT: "heartbeat",
    LogCategory.NOTIFICATIONS: "notifications",
    LogCategory.COMMANDS: "commands",
    LogCategory.MANAGEMENT: "management",
    LogCategory.PERFORMANCE: "performance",
    LogCategory.DEBUG: "debug",
}

DEFAULT_LOG_ROOT = Path("/var/log/ai-security")
FALLBACK_LOG_ROOT = Path.home() / ".local" / "state" / "ai-security" / "logs"
