"""
Command repository — append-only database storage for commands and lifecycle records.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.commands.exceptions import CommandRepositoryError
from management_server.commands.models import CommandState, RemoteCommand

logger = structlog.get_logger("commands.repository")


class CommandRepository:
    """Persists commands and lifecycle records (append-only)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_command(self, command: RemoteCommand) -> dict[str, Any]:
        """Store a new command."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                INSERT INTO commands (id, command_id, correlation_id, machine_id,
                    command_type, parameters_json, priority, state,
                    created_at, expires_at, requested_by, created_at_ts)
                VALUES (:id, :cid, :corr, :mid, :ct, :params, :pri, :state,
                    :created, :expires, :req, :now)
            """),
            {
                "id": str(uuid.uuid4()),
                "cid": command.command_id,
                "corr": command.correlation_id,
                "mid": command.machine_id,
                "ct": command.command_type,
                "params": json.dumps(command.parameters),
                "pri": command.priority.value,
                "state": command.state.value,
                "created": command.created_at,
                "expires": command.expires_at,
                "req": command.requested_by,
                "now": now,
            },
        )

        # Record initial lifecycle
        await self._record_lifecycle(command.command_id, CommandState.CREATED, CommandState.CREATED)

        await self._session.commit()
        return {"command_id": command.command_id}

    async def get_command(self, command_id: str) -> dict[str, Any] | None:
        """Get a command by ID."""
        result = await self._session.execute(
            text("SELECT * FROM commands WHERE command_id = :cid"),
            {"cid": command_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def update_state(
        self,
        command_id: str,
        new_state: CommandState,
        triggered_by: str = "system",
        reason: str = "",
    ) -> dict[str, Any]:
        """Update command state and record lifecycle event."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                UPDATE commands
                SET state = :state, updated_at = :now
                WHERE command_id = :cid
            """),
            {"cid": command_id, "state": new_state.value, "now": now},
        )

        await self._record_lifecycle(command_id, new_state, triggered_by, reason)
        await self._session.commit()

        result = await self.get_command(command_id)
        if result is None:
            raise CommandRepositoryError(f"Command not found after update: {command_id}")
        return result

    async def _record_lifecycle(
        self,
        command_id: str,
        to_state: CommandState,
        triggered_by: str = "system",
        reason: str = "",
    ) -> None:
        await self._session.execute(
            text("""
                INSERT INTO command_lifecycle (id, command_id, to_state, triggered_by, reason, created_at)
                VALUES (:id, :cid, :state, :by, :reason, :now)
            """),
            {
                "id": str(uuid.uuid4()),
                "cid": command_id,
                "state": to_state.value,
                "by": triggered_by,
                "reason": reason,
                "now": datetime.now(tz=UTC),
            },
        )

    async def get_pending_for_machine(
        self, machine_id: str, states: list[CommandState] | None = None
    ) -> list[dict[str, Any]]:
        """Get pending commands for a machine."""
        if states is None:
            states = [CommandState.AUTHORIZED, CommandState.READY]

        state_values = [s.value for s in states]
        placeholders = ", ".join(f":s{i}" for i in range(len(state_values)))
        params: dict[str, object] = {"mid": machine_id}
        for i, sv in enumerate(state_values):
            params[f"s{i}"] = sv
        result = await self._session.execute(
            text(f"""
                SELECT * FROM commands
                WHERE machine_id = :mid AND state IN ({placeholders})
                ORDER BY created_at ASC
            """),
            params,
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def list_commands(
        self,
        limit: int = 100,
        offset: int = 0,
        machine_id: str | None = None,
        state: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List commands with optional filters."""
        where_parts: list[str] = []
        params: dict[str, object] = {}
        if machine_id:
            where_parts.append("machine_id = :mid")
            params["mid"] = machine_id
        if state:
            where_parts.append("state = :state")
            params["state"] = state

        where = "WHERE " + " AND ".join(where_parts) if where_parts else ""

        count = await self._session.execute(text(f"SELECT COUNT(*) FROM commands {where}"), params)
        total = count.scalar() or 0

        params["limit"] = limit
        params["offset"] = offset
        result = await self._session.execute(
            text(
                f"SELECT * FROM commands {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        )
        return [dict(r._mapping) for r in result.fetchall()], total

    async def get_lifecycle(self, command_id: str) -> list[dict[str, Any]]:
        """Get lifecycle records for a command."""
        result = await self._session.execute(
            text("""
                SELECT * FROM command_lifecycle
                WHERE command_id = :cid
                ORDER BY created_at ASC
            """),
            {"cid": command_id},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def count_commands(self) -> int:
        result = await self._session.execute(text("SELECT COUNT(*) FROM commands"))
        return result.scalar() or 0

    async def count_by_state(self) -> dict[str, int]:
        result = await self._session.execute(
            text("SELECT state, COUNT(*) as cnt FROM commands GROUP BY state")
        )
        counts: dict[str, int] = {}
        for row in result.fetchall():
            counts[row.state] = row.cnt
        return counts
