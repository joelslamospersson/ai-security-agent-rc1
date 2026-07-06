"""
Report generator — generates incident, daily, weekly, and monthly reports.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from management_server.logging.exceptions import ReportError
from management_server.logging.formatter import LogFormatter
from management_server.logging.models import DailyReport, IncidentReport

logger = structlog.get_logger("logging.reports")


class ReportGenerator:
    """Generates human-readable reports."""

    def __init__(self, log_root: Path) -> None:
        self._log_root = log_root

    async def generate_incident_report(self, incident: IncidentReport) -> str:
        """Generate a formatted incident report."""
        lines = [
            "=" * 60,
            "INCIDENT REPORT",
            "=" * 60,
            "",
            f"Incident ID:    {incident.incident_id}",
            f"Correlation ID: {LogFormatter.mask_value(incident.correlation_id)}",
            f"Start Time:     {incident.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"End Time:       {incident.end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Duration:       {incident.duration_seconds:.1f}s",
            f"Source:         {LogFormatter.mask_value(incident.source)}",
            f"Attack Type:    {incident.attack_type}",
            "",
            "Detection Chain:",
        ]
        for i, step in enumerate(incident.detection_chain, 1):
            lines.append(f"  {i}. {step}")

        lines.extend(
            [
                "",
                f"Threat Score:   {incident.threat_score:.0f}",
                f"Confidence:     {incident.confidence:.0f}%",
                f"Policy:         {incident.policy}",
                "",
                "Firewall Actions:",
            ]
        )
        for action in incident.firewall_actions:
            lines.append(f"  - {action}")

        lines.extend(
            [
                "",
                "Notifications Sent:",
            ]
        )
        for n in incident.notifications_sent:
            lines.append(f"  - {n}")

        lines.extend(
            [
                "",
                f"Final Resolution: {incident.final_resolution}",
                "",
                "=" * 60,
            ]
        )
        return "\n".join(lines)

    async def generate_daily_report(self, report: DailyReport) -> str:
        """Generate a daily summary report."""
        lines = [
            "=" * 60,
            f"DAILY REPORT — {report.date}",
            "=" * 60,
            "",
            f"Total Detections:    {report.total_detections}",
            f"Critical Detections: {report.critical_detections}",
            f"Commands Executed:   {report.commands_executed}",
            f"Machines Online:     {report.machines_online}",
            f"Machines Offline:    {report.machines_offline}",
            f"Firewall Actions:    {report.firewall_actions}",
            f"Avg Response Time:   {report.average_response_time_ms:.1f}ms",
            "",
            "Top Attack Types:",
        ]
        for attack_type, count in report.top_attack_types:
            lines.append(f"  - {attack_type}: {count}")
        lines.extend(
            [
                "",
                "Top Offending IPs:",
            ]
        )
        for ip in report.top_offending_ips:
            lines.append(f"  - {LogFormatter.mask_value(ip)}")
        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    async def generate_weekly_report(self, daily_reports: list[DailyReport]) -> str:
        """Generate a weekly summary report from daily reports."""
        total = sum(r.total_detections for r in daily_reports)
        critical = sum(r.critical_detections for r in daily_reports)
        commands = sum(r.commands_executed for r in daily_reports)
        avg_response = sum(r.average_response_time_ms for r in daily_reports) / max(
            len(daily_reports), 1
        )

        lines = [
            "=" * 60,
            "WEEKLY REPORT",
            "=" * 60,
            "",
            f"Period: {daily_reports[0].date} — {daily_reports[-1].date}"
            if daily_reports
            else "Period: N/A",
            "",
            f"Total Detections:    {total}",
            f"Critical Detections: {critical}",
            f"Commands Executed:   {commands}",
            f"Avg Response Time:   {avg_response:.1f}ms",
            "",
            "=" * 60,
        ]
        return "\n".join(lines)

    async def generate_monthly_report(self, daily_reports: list[DailyReport]) -> str:
        """Generate a monthly summary report from daily reports."""
        return await self.generate_weekly_report(daily_reports)

    async def save_report(self, category: str, filename: str, content: str) -> Path:
        """Save a report to the reports directory."""
        report_dir = self._log_root / "reports" / category
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / filename
        try:
            path.write_text(content)
            logger.info("Report saved", path=str(path))
            return path
        except OSError as e:
            raise ReportError(f"Failed to save report: {e}") from e
