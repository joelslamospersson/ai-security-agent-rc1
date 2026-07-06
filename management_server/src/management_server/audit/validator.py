"""
Audit validator — validates audit events before persistence.
"""

from __future__ import annotations

import structlog

from management_server.audit.exceptions import AuditValidationError
from management_server.audit.models import (
    SUBSYSTEMS,
    AuditEvent,
    AuditOutcome,
    AuditSeverity,
)

logger = structlog.get_logger("audit.validator")

VALID_SEVERITIES = {s.value for s in AuditSeverity}
VALID_OUTCOMES = {o.value for o in AuditOutcome}


class AuditValidator:
    """Validates audit events before storage."""

    @staticmethod
    def validate(event: AuditEvent) -> list[str]:
        """Validate an audit event. Returns list of errors."""
        errors: list[str] = []

        if not event.audit_id:
            errors.append("audit_id is required")
        if not event.subsystem:
            errors.append("subsystem is required")
        elif event.subsystem not in SUBSYSTEMS:
            errors.append(f"Unknown subsystem: '{event.subsystem}'")
        if not event.event_type:
            errors.append("event_type is required")
        if event.severity.value not in VALID_SEVERITIES:
            errors.append(f"Invalid severity: '{event.severity.value}'")
        if event.outcome.value not in VALID_OUTCOMES:
            errors.append(f"Invalid outcome: '{event.outcome.value}'")

        return errors

    @staticmethod
    def validate_and_raise(event: AuditEvent) -> None:
        """Validate and raise on first error."""
        errors = AuditValidator.validate(event)
        if errors:
            raise AuditValidationError(errors[0])

    @staticmethod
    def verify_chain(events: list[AuditEvent]) -> tuple[bool, str]:
        """Verify hash chain integrity for a list of ordered events.

        Returns (is_valid, first_failed_audit_id).
        """
        if not events:
            return True, ""

        # Verify each event's own hash
        for _i, event in enumerate(events):
            if not event.verify_integrity():
                return False, event.audit_id

        # Verify chain links
        for i in range(1, len(events)):
            if events[i].previous_hash != events[i - 1].current_hash:
                return False, events[i].audit_id

        return True, ""
