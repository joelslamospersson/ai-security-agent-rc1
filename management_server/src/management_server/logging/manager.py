"""
Logging Manager — high-level facade for the Logging & Reporting Framework.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from management_server.logging.compression import LogCompressor
from management_server.logging.metrics import LoggingMetricsCollector
from management_server.logging.models import DailyReport, LogCategory
from management_server.logging.reports import ReportGenerator
from management_server.logging.retention import RetentionManager
from management_server.logging.rotation import LogRotator
from management_server.logging.service import LoggingService
from management_server.logging.writer import LogWriter

logger = structlog.get_logger("logging.manager")


class LoggingManager:
    """High-level facade for the Logging & Reporting Framework."""

    def __init__(self) -> None:
        self._writer = LogWriter()
        self._rotator = LogRotator(self._writer.log_root)
        self._compressor = LogCompressor(self._writer.log_root)
        self._retention = RetentionManager(self._writer.log_root)
        self._reporter = ReportGenerator(self._writer.log_root)
        self._metrics = LoggingMetricsCollector()
        self._service = LoggingService(
            writer=self._writer,
            rotator=self._rotator,
            compressor=self._compressor,
            retention=self._retention,
            reporter=self._reporter,
            metrics=self._metrics,
        )
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("Logging manager initialized")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def service(self) -> LoggingService:
        return self._service

    async def log(self, category: str, severity: str = "INFO", **kwargs: Any) -> dict[str, Any]:
        log_result: dict[str, Any] = await self._service.log(
            LogCategory(category), severity, **kwargs
        )
        return log_result

    async def rotate_logs(self) -> list[dict[str, Any]]:
        rotate_result: list[dict[str, Any]] = await self._service.rotate_logs()
        return rotate_result

    async def compress_logs(self, older_than_days: int = 1) -> list[dict[str, Any]]:
        compress_result: list[dict[str, Any]] = await self._service.compress_logs(older_than_days)
        return compress_result

    async def enforce_retention(self) -> dict[str, Any]:
        retention_result: dict[str, Any] = await self._service.enforce_retention()
        return retention_result

    async def generate_daily_report(self, report: DailyReport) -> Path:
        result: Path = await self._service.generate_daily_report(report)
        return result

    async def generate_weekly_report(self, daily_reports: list[DailyReport]) -> Path:
        result: Path = await self._service.generate_weekly_report(daily_reports)
        return result

    async def generate_monthly_report(self, daily_reports: list[DailyReport]) -> Path:
        result: Path = await self._service.generate_monthly_report(daily_reports)
        return result

    async def get_logs_list(self, category: str | None = None) -> list[dict[str, Any]]:
        log_result: list[dict[str, Any]] = await self._service.get_logs_list(category)
        return log_result

    async def get_reports_list(self, category: str = "daily") -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._service.get_reports_list(category)
        return result

    async def get_metrics(self) -> dict[str, int | float]:
        metrics_result: dict[str, int | float] = await self._service.get_metrics()
        return metrics_result
