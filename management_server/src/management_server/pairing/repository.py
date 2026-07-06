"""
Pairing token repository — database CRUD for pairing_tokens table.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.pairing.exceptions import PairingRepositoryError
from management_server.pairing.models import TokenState

logger = structlog.get_logger("pairing.repository")


class PairingRepository:
    """Persists and retrieves pairing token records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_token(
        self,
        token_id: str,
        token_hash: str,
        expires_at: datetime,
        creator: str = "system",
        machine_uuid: str | None = None,
        audit_reference: str = "",
    ) -> dict[str, Any]:
        """Create a new pairing token record."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                INSERT INTO pairing_tokens (id, token_id, token_hash, status,
                    created_at, expires_at, creator, machine_uuid, audit_reference)
                VALUES (:id, :token_id, :token_hash, :status,
                    :created_at, :expires_at, :creator, :machine_uuid, :audit_ref)
            """),
            {
                "id": str(uuid.uuid4()),
                "token_id": token_id,
                "token_hash": token_hash,
                "status": TokenState.ISSUED.value,
                "created_at": now,
                "expires_at": expires_at,
                "creator": creator,
                "machine_uuid": machine_uuid,
                "audit_ref": audit_reference,
            },
        )
        await self._session.commit()

        result = await self._get_by_token_id(token_id)
        assert result is not None
        return result

    async def get_by_token_id(self, token_id: str) -> dict[str, Any]:
        """Get a token record by its public token_id."""
        result = await self._get_by_token_id(token_id)
        if result is None:
            raise PairingRepositoryError(f"Token not found: {token_id}")
        return result

    async def _get_by_token_id(self, token_id: str) -> dict[str, Any] | None:
        """Internal — get token by token_id, return None if absent."""
        result = await self._session.execute(
            text("SELECT * FROM pairing_tokens WHERE token_id = :tid"),
            {"tid": token_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def get_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        """Find a token by its SHA-256 hash. O(1) hash lookup."""
        result = await self._session.execute(
            text("SELECT * FROM pairing_tokens WHERE token_hash = :th"),
            {"th": token_hash},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def update_status(
        self,
        token_id: str,
        new_status: TokenState,
        machine_uuid: str | None = None,
    ) -> dict[str, Any]:
        """Update a token's status. Returns updated record."""
        now = datetime.now(tz=UTC)

        consumed_at = now if new_status == TokenState.CONSUMED else None
        await self._session.execute(
            text("""
                UPDATE pairing_tokens
                SET status = :status,
                    consumed_at = :consumed_at,
                    machine_uuid = COALESCE(:machine_uuid, machine_uuid),
                    updated_at = :now
                WHERE token_id = :tid
            """),
            {
                "tid": token_id,
                "status": new_status.value,
                "consumed_at": consumed_at,
                "machine_uuid": machine_uuid,
                "now": now,
            },
        )
        await self._session.commit()

        result = await self._get_by_token_id(token_id)
        if result is None:
            raise PairingRepositoryError(f"Token not found after update: {token_id}")
        return result

    async def expire_pending_tokens(self) -> int:
        """Mark all PENDING tokens past TTL as EXPIRED. Returns count."""
        now = datetime.now(tz=UTC)
        result = await self._session.execute(
            text("""
                UPDATE pairing_tokens
                SET status = 'expired', updated_at = :now
                WHERE status IN ('issued', 'pending') AND expires_at < :now
            """),
            {"now": now},
        )
        await self._session.commit()
        # CursorResult has .rowcount attribute
        count_val = result.rowcount  # type: ignore[attr-defined]
        count: int = count_val if count_val is not None else 0
        return count

    async def expire_unused_tokens(self) -> int:
        """Mark all UNUSED tokens past TTL as EXPIRED. Returns count."""
        now = datetime.now(tz=UTC)
        result = await self._session.execute(
            text("""
                UPDATE pairing_tokens
                SET status = 'expired', updated_at = :now
                WHERE status = 'unused' AND expires_at < :now
            """),
            {"now": now},
        )
        await self._session.commit()
        # CursorResult has .rowcount attribute
        count_val = result.rowcount  # type: ignore[attr-defined]
        count: int = count_val if count_val is not None else 0
        return count

    async def revoke_token(self, token_id: str) -> dict[str, Any]:
        """Revoke a token. Returns updated record."""
        return await self.update_status(token_id, TokenState.REVOKED)

    async def list_tokens(
        self,
        status: TokenState | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List tokens with optional status filter and pagination."""
        where = "WHERE status = :status" if status else ""
        params: dict[str, object] = {}
        if status:
            params["status"] = status.value

        count_result = await self._session.execute(
            text(f"SELECT COUNT(*) FROM pairing_tokens {where}"),
            params,
        )
        total = count_result.scalar() or 0

        params["limit"] = limit
        params["offset"] = offset
        result = await self._session.execute(
            text(
                f"SELECT * FROM pairing_tokens {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        )
        return [dict(row._mapping) for row in result.fetchall()], total

    async def count_by_status(self) -> dict[str, int]:
        """Count tokens grouped by status."""
        result = await self._session.execute(
            text("SELECT status, COUNT(*) as cnt FROM pairing_tokens GROUP BY status")
        )
        counts: dict[str, int] = {}
        for row in result.fetchall():
            counts[row.status] = row.cnt
        return counts

    async def delete_token(self, token_id: str) -> None:
        """Hard-delete a token (testing/cleanup only)."""
        await self._session.execute(
            text("DELETE FROM pairing_tokens WHERE token_id = :tid"),
            {"tid": token_id},
        )
        await self._session.commit()
