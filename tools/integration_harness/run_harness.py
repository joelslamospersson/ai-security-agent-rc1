"""
Integration Test Harness — validates the complete AI Security Platform.

Usage:
    python run_harness.py --scenario all
    python run_harness.py --scenario ssh_brute_force
    python run_harness.py --benchmark
    python run_harness.py --list
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from integration_harness.benchmark import Benchmark
from integration_harness.metrics import MetricsCollector
from integration_harness.scenario_runner import ScenarioRunner


async def scenario_ssh_brute_force(runner: ScenarioRunner) -> None:
    await runner.run_attack_scenario("ssh_brute_force", lambda agent, attacker: [
        attacker.ssh_brute_force(attempts=50),
        attacker.ssh_brute_force(attempts=50),
    ])


async def scenario_password_spraying(runner: ScenarioRunner) -> None:
    await runner.run_attack_scenario("password_spraying", lambda agent, attacker: [
        attacker.password_spraying(),
    ])


async def scenario_port_scan(runner: ScenarioRunner) -> None:
    await runner.run_attack_scenario("port_scan", lambda agent, attacker: [
        attacker.port_scan(),
    ])


async def scenario_mixed_attack(runner: ScenarioRunner) -> None:
    await runner.run_attack_scenario("mixed_attack", lambda agent, attacker: [
        attacker.ssh_brute_force(attempts=30),
        attacker.password_spraying(),
        attacker.port_scan(),
        attacker.privilege_escalation(),
    ])


async def scenario_heartbeat_flow(runner: ScenarioRunner) -> None:
    """Test basic heartbeat flow without attacks."""
    async def actions(runner: ScenarioRunner) -> None:
        count_before = runner.management.heartbeat_count
        for _ in range(5):
            hb = runner.agent.create_heartbeat()
            await runner.management.process_heartbeat(hb)
        assert runner.management.heartbeat_count == count_before + 5

    await runner.run_scenario("heartbeat_flow", actions)


async def scenario_command_delivery(runner: ScenarioRunner) -> None:
    """Test command delivery via heartbeat."""
    async def actions(runner: ScenarioRunner) -> None:
        runner.management.add_pending_command("restart_agent", runner.agent.machine_uuid)
        runner.management.add_pending_command("reload_configuration", runner.agent.machine_uuid)

        for _ in range(3):
            hb = runner.agent.create_heartbeat()
            resp = await runner.management.process_heartbeat(hb)
            if resp.get("pending_commands"):
                for cmd in resp["pending_commands"]:
                    runner.agent.record_command_response(cmd["command_id"])

        runner.assertions.verify_command_chain(
            commands_created=runner.management.commands_pending,
            heartbeats_with_commands=runner.management.heartbeats_received,
        )

    await runner.run_scenario("command_delivery", actions)


async def scenario_network_partition(runner: ScenarioRunner) -> None:
    """Test network partition and recovery."""
    async def actions(runner: ScenarioRunner) -> None:
        before = []
        for _ in range(3):
            hb = runner.agent.create_heartbeat()
            resp = await runner.management.process_heartbeat(hb)
            before.append(resp)

        runner.network.partition()
        during = []
        for _ in range(3):
            hb = runner.agent.create_heartbeat()
            sim = await runner.network.simulate_request("management")
            if sim["success"]:
                resp = await runner.management.process_heartbeat(hb)
                during.append(resp)

        runner.network.heal()
        after = []
        for _ in range(3):
            hb = runner.agent.create_heartbeat()
            resp = await runner.management.process_heartbeat(hb)
            after.append(resp)

        runner.assertions.verify_failure_recovery(before, during, after)

    await runner.run_scenario("network_partition", actions)


SCENARIOS = {
    "ssh_brute_force": scenario_ssh_brute_force,
    "password_spraying": scenario_password_spraying,
    "port_scan": scenario_port_scan,
    "mixed_attack": scenario_mixed_attack,
    "heartbeat_flow": scenario_heartbeat_flow,
    "command_delivery": scenario_command_delivery,
    "network_partition": scenario_network_partition,
}


async def main() -> None:
    parser = argparse.ArgumentParser(description="AI Security Integration Test Harness")
    parser.add_argument("--scenario", default="all", help="Scenario to run (or 'all', 'list')")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmarks")
    parser.add_argument("--output", default="artifacts", help="Output directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for determinism")
    args = parser.parse_args()

    if args.scenario == "list":
        print("Available scenarios:")
        for name in sorted(SCENARIOS):
            print(f"  - {name}")
        return

    runner = ScenarioRunner()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.time()

    if args.benchmark:
        print("Running benchmarks...")
        metrics = MetricsCollector()
        bench = Benchmark(metrics)
        results = await bench.run_all(100)
        (output_dir / "benchmark.json").write_text(json.dumps(results, indent=2))
        print(json.dumps(results, indent=2))

    # Run scenarios
    if args.scenario == "all":
        scenarios_to_run = list(SCENARIOS.items())
    else:
        scenarios_to_run = [(args.scenario, SCENARIOS[args.scenario])]

    for name, scenario_fn in scenarios_to_run:
        print(f"Running scenario: {name}...")
        await scenario_fn(runner)

    # Generate report
    report = runner.generate_report()
    (output_dir / "report.json").write_text(
        json.dumps({
            "timestamp": report.timestamp,
            "passed": report.passed,
            "failed": report.failed,
            "errors": report.errors,
            "total_assertions": report.total_assertions,
            "passed_assertions": report.passed_assertions,
            "failed_assertions": report.failed_assertions,
            "scenarios": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "error": s.error,
                    "assertions": [
                        {"name": a.name, "result": a.result.value, "message": a.message}
                        for a in s.assertions
                    ],
                    "metrics": s.metrics,
                }
                for s in report.scenarios
            ],
        }, indent=2, default=str)
    )

    total_time = time.time() - t_start
    print(f"\n{'='*60}")
    print("Integration Test Harness Results")
    print(f"{'='*60}")
    print(f"Total: {report.total}  Passed: {report.passed}  "
          f"Failed: {report.failed}  Errors: {report.errors}")
    print(f"Assertions: {report.passed_assertions}/{report.total_assertions} passed")
    print(f"Duration: {total_time:.2f}s")
    print(f"Report: {output_dir / 'report.json'}")
    print(f"{'='*60}")

    sys.exit(0 if report.failed == 0 and report.errors == 0 else 1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
