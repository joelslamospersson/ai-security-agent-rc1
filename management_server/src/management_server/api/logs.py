"""
Logging API endpoints.

GET    /api/v1/logs                  — List log files
GET    /api/v1/logs/reports          — List reports
POST   /api/v1/logs/report/daily     — Generate daily report
POST   /api/v1/logs/report/weekly    — Generate weekly report
POST   /api/v1/logs/report/monthly   — Generate monthly report
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from management_server.logging.manager import LoggingManager
from management_server.logging.models import DailyReport

router = APIRouter(prefix="/api/v1", tags=["logs"])


async def _get_logging_manager(request: Request) -> LoggingManager:
    mgr: LoggingManager | None = getattr(request.app.state, "logging_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Logging manager not initialized")
    return mgr


@router.get("/logs", summary="List log files")
async def list_logs(
    category: str | None = Query(default=None),
    manager: LoggingManager = Depends(_get_logging_manager),  # noqa: B008
) -> list[dict[str, Any]]:
    """List available log files, optionally filtered by category."""
    log_result: list[dict[str, Any]] = await manager.get_logs_list(category)
    return log_result


@router.get("/logs/reports", summary="List reports")
async def list_reports(
    category: str = Query(default="daily"),
    manager: LoggingManager = Depends(_get_logging_manager),  # noqa: B008
) -> list[dict[str, Any]]:
    """List available reports."""
    report_result: list[dict[str, Any]] = await manager.get_reports_list(category)
    return report_result


@router.post("/logs/report/daily", summary="Generate daily report")
async def generate_daily_report(
    manager: LoggingManager = Depends(_get_logging_manager),  # noqa: B008
) -> dict[str, Any]:
    """Generate a daily summary report."""
    from datetime import UTC, datetime

    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    report = DailyReport(date=today)
    path = await manager.generate_daily_report(report)
    return {"path": str(path), "date": today}


@router.post("/logs/report/weekly", summary="Generate weekly report")
async def generate_weekly_report(
    manager: LoggingManager = Depends(_get_logging_manager),  # noqa: B008
) -> dict[str, Any]:
    """Generate a weekly summary report."""
    path = await manager.generate_weekly_report([DailyReport()])
    return {"path": str(path)}


@router.post("/logs/report/monthly", summary="Generate monthly report")
async def generate_monthly_report(
    manager: LoggingManager = Depends(_get_logging_manager),  # noqa: B008
) -> dict[str, Any]:
    """Generate a monthly summary report."""
    path = await manager.generate_monthly_report([DailyReport()])
    return {"path": str(path)}
