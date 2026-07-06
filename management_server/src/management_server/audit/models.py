"""
Audit models — immutable AuditEvent with SHA-256 hash chaining.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Any
from uuid import uuid4


class AuditSeverity(StrEnum):
    """Severity of an audit event."""

    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


class AuditOutcome(StrEnum):
    """Outcome of the audited operation."""

    SUCCESS = auto()
    FAILURE = auto()
    PENDING = auto()
    SKIPPED = auto()


SUBSYSTEMS = {
    "certificates",
    "machines",
    "pairing",
    "heartbeat",
    "policies",
    "routing",
    "notifications",
    "audit",
    "system",
}

EVENT_TYPES = {
    "registration",
    "approval",
    "rejection",
    "certificate_issue",
    "certificate_revoke",
    "heartbeat",
    "policy_assignment",
    "routing_decision",
    "notification",
    "login",
    "pairing",
    "configuration_change",
    "capability_change",
    "machine_offline",
    "machine_online",
    "export",
    "retention",
}


@dataclass(frozen=True)
class AuditEvent:
    """Immutable audit event with hash chain integrity."""

    audit_id: str = ""
    correlation_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    machine_id: str = ""
    subsystem: str = ""
    actor: str = "system"
    event_type: str = ""
    severity: AuditSeverity = AuditSeverity.INFO
    outcome: AuditOutcome = AuditOutcome.SUCCESS
    description: str = ""
    metadata_json: str = "{}"
    current_hash: str = ""
    previous_hash: str = ""

    @classmethod
    def create(
        cls,
        subsystem: str,
        event_type: str,
        description: str = "",
        machine_id: str = "",
        actor: str = "system",
        severity: AuditSeverity = AuditSeverity.INFO,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        correlation_id: str = "",
        metadata: dict[str, Any] | None = None,
        previous_hash: str = "",
    ) -> AuditEvent:
        """Create a new audit event with hash."""
        audit_id = uuid4().hex[:16]
        ts = datetime.now(tz=UTC)
        meta_json = json.dumps(metadata or {}, default=str, sort_keys=True)

        # Build content for hashing
        content = (
            f"{audit_id}|{correlation_id}|{ts.isoformat()}|{machine_id}|"
            f"{subsystem}|{actor}|{event_type}|{severity.value}|{outcome.value}|"
            f"{description}|{meta_json}|{previous_hash}"
        )
        current_hash = hashlib.sha256(content.encode()).hexdigest()

        return cls(
            audit_id=audit_id,
            correlation_id=correlation_id,
            timestamp=ts,
            machine_id=machine_id,
            subsystem=subsystem,
            actor=actor,
            event_type=event_type,
            severity=severity,
            outcome=outcome,
            description=description,
            metadata_json=meta_json,
            current_hash=current_hash,
            previous_hash=previous_hash,
        )

    def compute_hash(self) -> str:
        """Recompute the hash of this event. Used for integrity verification."""
        content = (
            f"{self.audit_id}|{self.correlation_id}|{self.timestamp.isoformat()}|{self.machine_id}|"
            f"{self.subsystem}|{self.actor}|{self.event_type}|{self.severity.value}|{self.outcome.value}|"
            f"{self.description}|{self.metadata_json}|{self.previous_hash}"
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify that this event's hash matches its content."""
        return self.current_hash == self.compute_hash()


@dataclass
class RetentionPolicy:
    """Configurable audit retention policy."""

    retention_days: int = 365
    max_records: int = 1_000_000

    @property
    def cutoff_date(self) -> datetime:
        from datetime import timedelta

        return datetime.now(tz=UTC) - timedelta(days=self.retention_days)

    def should_retain(self, event_timestamp: datetime) -> bool:
        return event_timestamp >= self.cutoff_date
