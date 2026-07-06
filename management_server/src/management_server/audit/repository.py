"""
Audit repository — append-only storage for audit events.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.audit.models import AuditEvent

logger = structlog.get_logger("audit.repository")


class AuditRepository:
    """Append-only audit event storage."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, event: AuditEvent) -> dict[str, Any]:
        """Append an audit event (write-once)."""
        await self._session.execute(
            text("""
                INSERT INTO audit_events (id, audit_id, correlation_id, timestamp,
                    machine_id, subsystem, actor, event_type, severity, outcome,
                    description, metadata_json, current_hash, previous_hash, created_at)
                VALUES (:id, :aid, :cid, :ts, :mid, :sub, :act, :et, :sev, :out,
                    :desc, :meta, :ch, :ph, :now)
            """),
            {
                "id": str(uuid.uuid4()),
                "aid": event.audit_id,
                "cid": event.correlation_id,
                "ts": event.timestamp,
                "mid": event.machine_id,
                "sub": event.subsystem,
                "act": event.actor,
                "et": event.event_type,
                "sev": event.severity.value,
                "out": event.outcome.value,
                "desc": event.description,
                "meta": event.metadata_json,
                "ch": event.current_hash,
                "ph": event.previous_hash,
                "now": datetime.now(tz=UTC),
            },
        )
        await self._session.commit()
        return {"audit_id": event.audit_id, "current_hash": event.current_hash}

    async def get(self, audit_id: str) -> dict[str, Any] | None:
        """Get an audit event by ID."""
        result = await self._session.execute(
            text("SELECT * FROM audit_events WHERE audit_id = :aid"),
            {"aid": audit_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def get_last(self) -> dict[str, Any] | None:
        """Get the most recent audit event (for hash chaining)."""
        result = await self._session.execute(
            text("""
                SELECT * FROM audit_events
                ORDER BY created_at DESC
                LIMIT 1
            """)
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def get_ordered(
        self,
        limit: int = 1000,
        offset: int = 0,
        subsystem: str | None = None,
        event_type: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get ordered audit events with optional filters."""
        where_parts: list[str] = []
        params: dict[str, object] = {}

        if subsystem:
            where_parts.append("subsystem = :sub")
            params["sub"] = subsystem
        if event_type:
            where_parts.append("event_type = :et")
            params["et"] = event_type

        where = ""
        if where_parts:
            where = "WHERE " + " AND ".join(where_parts)

        count_result = await self._session.execute(
            text(f"SELECT COUNT(*) FROM audit_events {where}"),
            params,
        )
        total = count_result.scalar() or 0

        params["limit"] = limit
        params["offset"] = offset
        result = await self._session.execute(
            text(f"""
                SELECT * FROM audit_events {where}
                ORDER BY created_at ASC
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
        rows = [dict(r._mapping) for r in result.fetchall()]
        return rows, total

    async def get_events_since(self, since: datetime) -> list[dict[str, Any]]:
        """Get all events since a given timestamp (for export)."""
        result = await self._session.execute(
            text("""
                SELECT * FROM audit_events
                WHERE created_at >= :since
                ORDER BY created_at ASC
            """),
            {"since": since},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def get_events_between(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        result = await self._session.execute(
            text("""
                SELECT * FROM audit_events
                WHERE created_at >= :start AND created_at <= :end
                ORDER BY created_at ASC
            """),
            {"start": start, "end": end},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def count_events(self) -> int:
        result = await self._session.execute(text("SELECT COUNT(*) FROM audit_events"))
        return result.scalar() or 0

    async def count_older_than(self, days: int) -> int:
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
        result = await self._session.execute(
            text("SELECT COUNT(*) FROM audit_events WHERE created_at < :cutoff"),
            {"cutoff": cutoff},
        )
        return result.scalar() or 0
