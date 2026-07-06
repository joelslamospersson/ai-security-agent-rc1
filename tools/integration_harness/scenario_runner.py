"""
Scenario runner — orchestrates scenario execution, assertions, and reporting.
"""

from __future__ import annotations

import time
from typing import Any

from integration_harness.assertions import AssertionEngine
from integration_harness.fake_agent import FakeAgent
from integration_harness.fake_attacker import FakeAttacker
from integration_harness.fake_discord import FakeDiscordAdapter
from integration_harness.fake_management import FakeManagementServer
from integration_harness.fake_network import FakeNetwork
from integration_harness.metrics import MetricsCollector
from integration_harness.models import (
    AssertionResult,
    HarnessReport,
    ScenarioResult,
    ScenarioStatus,
)
from integration_harness.replay import ScenarioRecorder


class ScenarioRunner:
    """Runs integration test scenarios with full validation."""

    def __init__(self) -> None:
        self.agent = FakeAgent()
        self.management = FakeManagementServer()
        self.discord = FakeDiscordAdapter()
        self.network = FakeNetwork()
        self.assertions = AssertionEngine()
        self.metrics = MetricsCollector()
        self.recorder = ScenarioRecorder()
        self.results: list[ScenarioResult] = []

    async def run_scenario(self, name: str, actions: Any) -> ScenarioResult:
        """Run a single scenario with validation."""
        result = ScenarioResult(name=name, status=ScenarioStatus.RUNNING)
        result.start_time = time.time()
        self.recorder.start()
        self.recorder.record("scenario_start", "harness", {"name": name})

        try:
            await actions(self)
            result.status = ScenarioStatus.PASSED
        except AssertionError as e:
            result.status = ScenarioStatus.FAILED
            result.error = str(e)
        except Exception as e:
            result.status = ScenarioStatus.ERROR
            result.error = f"{type(e).__name__}: {e}"

        result.end_time = time.time()
        result.assertions = self.assertions.results
        result.metrics = self.metrics.to_dict()

        self.recorder.record("scenario_end", "harness", {
            "status": result.status.value,
            "duration": result.end_time - result.start_time,
        })
        self.recorder.save(name)

        self.results.append(result)
        return result

    async def run_attack_scenario(self, name: str, attack_fn: Any) -> ScenarioResult:
        """Run a scenario where an attack is detected and traced."""
        async def actions(runner: ScenarioRunner) -> None:
            # Generate attack events
            attack_events = attack_fn(runner.agent, FakeAttacker())
            runner.recorder.record("attack", "attacker", {"count": len(attack_events)})

            # Send heartbeats (simulate agent activity)
            hbs = []
            for _ in range(3):
                hb = runner.agent.create_heartbeat(
                    event_queue_size=len(attack_events),
                    detection_queue_size=len(attack_events) // 2,
                )
                resp = await runner.management.process_heartbeat(hb)
                hbs.append(resp)
                runner.recorder.record("heartbeat", "agent", hb)

            # Render notifications via Discord
            for hb_resp in hbs:
                notif = {
                    "event_type": "attack_detected",
                    "severity": "critical" if len(attack_events) > 10 else "warning",
                    "machine_id": runner.agent.machine_uuid,
                    "payload": f"Detected {len(attack_events)} attack events",
                }
                await runner.discord.render_notification(notif)
                runner.recorder.record("notification", "discord", notif)

            # Verify the complete chain
            runner.assertions.verify_attack_detection_chain(
                attacker_events=attack_events,
                management_heartbeats=runner.management.heartbeats_received,
                audit_events=runner.management.audit_events,
                discord_notifications=runner.discord.notifications_rendered,
            )

            for assertion in runner.assertions.results:
                if assertion.result == AssertionResult.FAIL:
                    raise AssertionError(f"Assertion failed: {assertion.name}: {assertion.message}")

        return await self.run_scenario(name, actions)

    def generate_report(self) -> HarnessReport:
        """Generate a complete harness report."""
        from datetime import UTC, datetime
        report = HarnessReport(
            timestamp=datetime.now(tz=UTC).isoformat(),
            scenarios=list(self.results),
            total=len(self.results),
        )
        for r in self.results:
            if r.status == ScenarioStatus.PASSED:
                report.passed += 1
            elif r.status == ScenarioStatus.FAILED:
                report.failed += 1
            elif r.status == ScenarioStatus.ERROR:
                report.errors += 1
            for a in r.assertions:
                report.total_assertions += 1
                if a.result == AssertionResult.PASS:
                    report.passed_assertions += 1
                elif a.result == AssertionResult.FAIL:
                    report.failed_assertions += 1
        return report
