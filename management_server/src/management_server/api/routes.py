"""
API routes for the Management Server.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Request, Response

from management_server.version import get_version_info

router = APIRouter()

_startup_monotonic: float = 0.0


def set_startup_time() -> None:
    """Record the monotonic timestamp when the server started."""
    global _startup_monotonic
    _startup_monotonic = time.monotonic()


def _get_uptime() -> float:
    """Return uptime in seconds since process start (never negative)."""
    if _startup_monotonic <= 0:
        return 0.0
    return round(max(0.0, time.monotonic() - _startup_monotonic), 2)


@router.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "AI Security Management Server",
        "status": "running",
    }


@router.get("/health")
async def health_get(request: Request) -> dict[str, object]:
    """Health check endpoint — GET returns full status."""
    return await _build_health_response(request)


@router.head("/health", include_in_schema=False)
async def health_head(request: Request) -> Response:
    """Health check endpoint — HEAD returns 200 with no body.

    Compatible with load balancers, reverse proxies, and monitoring
    systems (Prometheus, HAProxy, UptimeRobot, BetterStack, etc.).
    Internally verifies the server is healthy.
    """
    await _build_health_response(request)
    return Response(status_code=200, media_type="application/json")


async def _build_health_response(request: Request) -> dict[str, object]:
    """Build the health check response dict."""
    result: dict[str, object] = {
        "status": "healthy",
        "application": "ai-security-management-server",
        "version": get_version_info()["version"],
        "uptime_seconds": _get_uptime(),
    }

    # Database status
    db = getattr(request.app.state, "db", None)
    if db is not None and db.is_initialized:
        try:
            db_status = await db.health_check()
            result["database"] = db_status
        except Exception as e:
            result["database"] = {"connected": False, "error": str(e)}
            result["status"] = "degraded"
    else:
        result["database"] = {"connected": False, "migration_version": None}
        result["status"] = "degraded"

    # Health supervisor report
    hs = getattr(request.app.state, "health_supervisor", None)
    if hs is not None:
        report = hs.get_report()
        result["subsystems"] = {
            name: {"state": h.state.value, "message": h.message}
            for name, h in report.subsystems.items()
        }
        result["healthy_count"] = report.healthy_count
        result["degraded_count"] = report.degraded_count
        result["failed_count"] = report.failed_count

        if report.overall.value == "failed":
            result["status"] = "failed"
        elif report.overall.value == "degraded":
            result["status"] = "degraded"

    # Emergency mode
    em = getattr(request.app.state, "emergency_mode", None)
    if em is not None:
        result["emergency_mode"] = em.to_dict()

    # Startup stages
    startup_report = getattr(request.app.state, "startup_report", None)
    if startup_report:
        result["startup"] = startup_report.to_dict()

    return result


@router.get("/version")
async def version() -> dict[str, str]:
    """Version endpoint."""
    return get_version_info()  # type: ignore[no-any-return]
