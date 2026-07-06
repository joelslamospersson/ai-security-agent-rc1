"""
Startup report generator — produces formatted startup summary.
"""

from __future__ import annotations

from management_server.startup.models import InitState, StartupReport

STATUS_INDICATORS = {
    InitState.READY: "✅ OK",
    InitState.FAILED: "❌ FAILED",
    InitState.SKIPPED: "⏭ SKIPPED",
    InitState.INITIALIZING: "⏳ INITIALIZING",
    InitState.PENDING: "⏳ PENDING",
}


def print_startup_report(report: StartupReport) -> None:
    """Print a formatted startup report to stdout."""
    lines = [
        "",
        "─" * 50,
        "  AI SECURITY — MANAGEMENT SERVER STARTUP",
        "─" * 50,
        "",
    ]

    lines.extend(_section("configuration", report))
    lines.extend(_section("logging", report))
    lines.extend(_section("database", report))
    lines.extend(_section("certificates", report))
    lines.extend(_section("machines", report))
    lines.extend(_section("pairing", report))
    lines.extend(_section("heartbeat", report))
    lines.extend(_section("policies", report))
    lines.extend(_section("routing", report))
    lines.extend(_section("notifications", report))
    lines.extend(_section("audit", report))
    lines.extend(_section("commands", report))
    lines.extend(_section("configsync", report))
    lines.extend(_section("discord", report))

    lines.append("─" * 50)

    if report.any_failed:
        lines.append("  ❌ STARTUP FAILED — See errors above")
    elif report.all_ready:
        lines.append("  ✅ READY — All subsystems operational")
    else:
        degraded = [n for n, s in report.stages.items() if s.state == InitState.SKIPPED]
        if degraded:
            lines.append(f"  ⚠️  DEGRADED — Subsystems skipped: {', '.join(degraded)}")
        else:
            lines.append("  ⚠️  DEGRADED — Some subsystems not ready")

    lines.append("─" * 50)
    lines.append("")

    print("\n".join(lines))


def _section(name: str, report: StartupReport) -> list[str]:
    """Format a single section of the startup report."""
    stage = report.stages.get(name.lower().replace(" ", "_"))
    if stage is None:
        return [f"  {name:<20}  —  NOT FOUND"]

    indicator = STATUS_INDICATORS.get(stage.state, "❓ UNKNOWN")
    error_suffix = f"  ({stage.error})" if stage.error else ""
    return [f"  {name:<20}  {indicator}{error_suffix}"]
