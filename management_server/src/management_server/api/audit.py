"""
Audit API endpoints for the Management Server.

GET    /api/v1/audit                — List audit events
GET    /api/v1/audit/{id}           — Get audit event
GET    /api/v1/audit/verify         — Verify hash chain integrity
POST   /api/v1/audit/export         — Export audit events
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from management_server.audit.manager import AuditManager
from management_server.audit.schemas import (
    AuditEventSchema,
    AuditExportRequest,
    AuditExportResponse,
    AuditVerifyResponse,
    ErrorResponse,
)

router = APIRouter(prefix="/api/v1", tags=["audit"])


async def _get_audit_manager(request: Request) -> AuditManager:
    mgr: AuditManager | None = getattr(request.app.state, "audit_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Audit manager not initialized")
    return mgr


@router.get(
    "/audit",
    summary="List audit events",
)
async def list_audit_events(
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    subsystem: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    manager: AuditManager = Depends(_get_audit_manager),  # noqa: B008
) -> dict[str, Any]:
    """List audit events with optional filters."""
    result: dict[str, Any] = await manager.list_events(
        limit=limit,
        offset=offset,
        subsystem=subsystem,
        event_type=event_type,
    )
    return result


@router.get(
    "/audit/{audit_id}",
    response_model=AuditEventSchema,
    responses={404: {"model": ErrorResponse}},
    summary="Get an audit event",
)
async def get_audit_event(
    audit_id: str,
    manager: AuditManager = Depends(_get_audit_manager),  # noqa: B008
) -> AuditEventSchema:
    """Get a specific audit event by ID."""
    event = await manager.get_event(audit_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Audit event not found: {audit_id}")
    return event


@router.get(
    "/audit/verify",
    response_model=AuditVerifyResponse,
    summary="Verify audit hash chain integrity",
)
async def verify_audit_chain(
    manager: AuditManager = Depends(_get_audit_manager),  # noqa: B008
) -> AuditVerifyResponse:
    """Verify the integrity of the entire audit hash chain."""
    return await manager.verify_integrity()


@router.post(
    "/audit/export",
    response_model=AuditExportResponse,
    summary="Export audit events",
)
async def export_audit_events(
    body: AuditExportRequest,
    manager: AuditManager = Depends(_get_audit_manager),  # noqa: B008
) -> AuditExportResponse:
    """Export audit events in the requested format."""
    try:
        return await manager.export_events(
            format_name=body.format,
            start_date=body.start_date,
            end_date=body.end_date,
            subsystem=body.subsystem,
            event_type=body.event_type,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
