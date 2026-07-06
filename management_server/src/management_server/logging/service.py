"""
Logging service — orchestrates logging, rotation, compression, retention, and reports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from management_server.logging.compression import LogCompressor
from management_server.logging.metrics import LoggingMetricsCollector
from management_server.logging.models import (
    DailyReport,
    IncidentReport,
    LogCategory,
    LogEntry,
)
from management_server.logging.reports import ReportGenerator
from management_server.logging.retention import RetentionManager
from management_server.logging.rotation import LogRotator
from management_server.logging.writer import LogWriter

logger = structlog.get_logger("logging.service")


class LoggingService:
    """Orchestrates the Logging & Reporting Framework."""

    def __init__(
        self,
        writer: LogWriter | None = None,
        rotator: LogRotator | None = None,
        compressor: LogCompressor | None = None,
        retention: RetentionManager | None = None,
        reporter: ReportGenerator | None = None,
        metrics: LoggingMetricsCollector | None = None,
    ) -> None:
        self._writer = writer or LogWriter()
        self._rotator = rotator or LogRotator(self._writer.log_root)
        self._compressor = compressor or LogCompressor(self._writer.log_root)
        self._retention = retention or RetentionManager(self._writer.log_root)
        self._reporter = reporter or ReportGenerator(self._writer.log_root)
        self._metrics = metrics or LoggingMetricsCollector()

    async def log(
        self,
        category: LogCategory | str,
        severity: str = "INFO",
        event_type: str = "",
        description: str = "",
        machine_id: str = "",
        correlation_id: str = "",
        source: str = "",
        threat_score: float = 0.0,
        confidence: float = 0.0,
        policy: str = "",
        action: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write a log entry."""
        if isinstance(category, str):
            category = LogCategory(category)

        entry = LogEntry(
            category=category,
            severity=severity,
            event_type=event_type,
            description=description,
            machine_id=machine_id,
            correlation_id=correlation_id,
            source=source,
            threat_score=threat_score,
            confidence=confidence,
            policy=policy,
            action=action,
            metadata=metadata or {},
        )
        result: dict[str, Any] = await self._writer.write(entry)
        self._metrics.entry_written(result.get("bytes_written", 0))
        return result

    async def log_security(
        self,
        event_type: str,
        description: str,
        machine_id: str = "",
        threat_score: float = 0.0,
        confidence: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return await self.log(
            LogCategory.SECURITY,
            "CRITICAL" if threat_score > 80 else "WARNING",
            event_type,
            description,
            machine_id=machine_id,
            threat_score=threat_score,
            confidence=confidence,
            **kwargs,
        )

    async def rotate_logs(self) -> list[dict[str, Any]]:
        """Rotate all log files."""
        results: list[dict[str, Any]] = await self._rotator.rotate_all()
        for _ in results:
            self._metrics.file_rotated()
        return results

    async def compress_logs(self, older_than_days: int = 1) -> list[dict[str, Any]]:
        """Compress rotated logs."""
        results: list[dict[str, Any]] = await self._compressor.compress_all(older_than_days)
        for r in results:
            if not r.get("skipped"):
                self._metrics.bytes_compressed(
                    r.get("original_bytes", 0), r.get("compressed_bytes", 0)
                )
        return results

    async def enforce_retention(self) -> dict[str, Any]:
        """Enforce retention policy."""
        result: dict[str, Any] = await self._retention.enforce()
        self._metrics.file_deleted(result.get("deleted_files", 0))
        return result

    async def generate_incident_report(self, incident: IncidentReport) -> Path:
        """Generate and save an incident report."""
        content = await self._reporter.generate_incident_report(incident)
        filename = f"incident_{incident.incident_id}_{datetime.now(tz=UTC).strftime('%Y%m%d')}.txt"
        path: Path = await self._reporter.save_report("incidents", filename, content)
        self._metrics.report_generated()
        return path

    async def generate_daily_report(self, report: DailyReport) -> Path:
        """Generate and save a daily report."""
        content = await self._reporter.generate_daily_report(report)
        filename = f"{report.date}.txt"
        path: Path = await self._reporter.save_report("daily", filename, content)
        self._metrics.report_generated()
        return path

    async def generate_weekly_report(self, daily_reports: list[DailyReport]) -> Path:
        """Generate and save a weekly report."""
        from datetime import UTC, datetime

        week_num = datetime.now(tz=UTC).isocalendar()[1]
        content = await self._reporter.generate_weekly_report(daily_reports)
        filename = f"week_{week_num}.txt"
        path: Path = await self._reporter.save_report("weekly", filename, content)
        self._metrics.report_generated()
        return path

    async def generate_monthly_report(self, daily_reports: list[DailyReport]) -> Path:
        """Generate and save a monthly report."""
        now = datetime.now(tz=UTC)
        content = await self._reporter.generate_monthly_report(daily_reports)
        filename = f"{now.year}_{now.strftime('%m')}.txt"
        path: Path = await self._reporter.save_report("monthly", filename, content)
        self._metrics.report_generated()
        return path

    async def get_logs_list(self, category: str | None = None) -> list[dict[str, Any]]:
        """List available log files."""
        root = self._writer.log_root
        logs: list[dict[str, Any]] = []

        search_dir = root / (
            LOG_DIRECTORIES.get(LogCategory(category), category) if category else ""
        )
        if not search_dir.exists():
            return logs

        for path in sorted(search_dir.iterdir()):
            if path.is_file():
                logs.append(
                    {
                        "name": path.name,
                        "path": str(path),
                        "size_bytes": path.stat().st_size,
                        "modified": datetime.fromtimestamp(
                            path.stat().st_mtime, tz=UTC
                        ).isoformat(),
                    }
                )
        return logs

    async def get_reports_list(self, category: str = "daily") -> list[dict[str, Any]]:
        """List available reports."""
        report_dir = self._writer.log_root / "reports" / category
        if not report_dir.exists():
            return []
        reports: list[dict[str, Any]] = []
        for path in sorted(report_dir.iterdir()):
            if path.is_file():
                reports.append(
                    {
                        "name": path.name,
                        "path": str(path),
                        "size_bytes": path.stat().st_size,
                        "modified": datetime.fromtimestamp(
                            path.stat().st_mtime, tz=UTC
                        ).isoformat(),
                    }
                )
        return reports

    async def get_metrics(self) -> dict[str, int | float]:
        snap = self._metrics.snapshot()
        return {
            "log_entries_written": snap.log_entries_written,
            "reports_generated": snap.reports_generated,
            "bytes_written": snap.bytes_written,
            "bytes_compressed": snap.bytes_compressed,
            "files_rotated": snap.files_rotated,
            "files_deleted": snap.files_deleted,
            "compression_ratio": snap.compression_ratio,
        }


LOG_DIRECTORIES = {
    "security": "security",
    "audit": "audit",
    "firewall": "firewall",
    "heartbeat": "heartbeat",
    "notifications": "notifications",
    "commands": "commands",
    "management": "management",
    "performance": "performance",
    "debug": "debug",
}
