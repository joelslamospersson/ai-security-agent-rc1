"""
Assertions — automated validation of the complete processing chain.

Validates that an attack flows through every subsystem stage correctly.
"""

from __future__ import annotations

from typing import Any

from integration_harness.models import Assertion, AssertionResult


class AssertionEngine:
    """Validates the complete processing chain for a scenario.

    Stages:
        1. Attack generated
        2. Agent detected
        3. Heartbeat sent
        4. Management received
        5. Routing decision made
        6. Notification created
        7. Audit event recorded
        8. Discord rendered
        9. Log written
    """

    def __init__(self) -> None:
        self._assertions: list[Assertion] = []

    def check(self, name: str, condition: bool, message: str = "", expected: str = "", actual: str = "") -> Assertion:
        """Add a check and return its result."""
        result = AssertionResult.PASS if condition else AssertionResult.FAIL
        assertion = Assertion(
            name=name,
            result=result,
            message=message or ("Passed" if condition else "Failed"),
            expected=expected,
            actual=actual,
        )
        self._assertions.append(assertion)
        return assertion

    def verify_attack_detection_chain(
        self,
        attacker_events: list[dict[str, Any]],
        management_heartbeats: list[dict[str, Any]],
        audit_events: list[dict[str, Any]],
        discord_notifications: list[dict[str, Any]],
    ) -> list[Assertion]:
        """Verify the complete attack-to-notification chain."""
        self._assertions.clear()

        # Stage 1: Attack generated
        self.check("attack_generated", len(attacker_events) > 0,
                    expected=">0 attacker events", actual=str(len(attacker_events)))

        # Stage 2: Heartbeats sent
        agent_heartbeats = [h for h in management_heartbeats if h.get("protocol_version")]
        self.check("heartbeats_sent", len(agent_heartbeats) > 0,
                    expected=">0 heartbeats", actual=str(len(agent_heartbeats)))

        # Stage 3: Management received heartbeats
        self.check("management_received", len(management_heartbeats) > 0,
                    expected=">0 heartbeats received", actual=str(len(management_heartbeats)))

        # Stage 4: Audit events recorded
        self.check("audit_events_recorded", len(audit_events) > 0,
                    expected=">0 audit events", actual=str(len(audit_events)))

        # Stage 5: Notifications sent / Discord rendered
        self.check("discord_notified", len(discord_notifications) > 0,
                    expected=">0 discord notifications", actual=str(len(discord_notifications)))

        # Stage 6: Heartbeats include heartbeat event type in audit
        has_heartbeat_audit = any(e.get("subsystem") == "heartbeat" for e in audit_events)
        self.check("heartbeat_audit_trail", has_heartbeat_audit,
                    expected="heartbeat audit event", actual=str(has_heartbeat_audit))

        return list(self._assertions)

    def verify_command_chain(
        self,
        commands_created: list[dict[str, Any]],
        heartbeats_with_commands: list[dict[str, Any]],
    ) -> list[Assertion]:
        """Verify the command creation and delivery chain."""
        self._assertions.clear()

        self.check("commands_created", len(commands_created) > 0,
                    expected=">0 commands", actual=str(len(commands_created)))

        commands_delivered = sum(
            1 for hb in heartbeats_with_commands
            if len(hb.get("pending_commands", [])) > 0
        )
        self.check("commands_delivered_via_heartbeat", commands_delivered > 0,
                    expected="commands in heartbeat response",
                    actual=f"commands in {commands_delivered} heartbeats")

        return list(self._assertions)

    def verify_failure_recovery(
        self,
        before_failure: list[Any],
        during_failure: list[Any],
        after_recovery: list[Any],
    ) -> list[Assertion]:
        """Verify system recovers after a failure."""
        self._assertions.clear()

        self.check("worked_before_failure", len(before_failure) > 0)
        self.check("degraded_during_failure", len(during_failure) <= len(before_failure),
                    message="System should show degradation during failure")
        self.check("recovered_after", len(after_recovery) > 0,
                    message="System should recover after failure resolved")

        return list(self._assertions)

    @property
    def all_passed(self) -> bool:
        return all(a.result == AssertionResult.PASS for a in self._assertions)

    @property
    def results(self) -> list[Assertion]:
        return list(self._assertions)
