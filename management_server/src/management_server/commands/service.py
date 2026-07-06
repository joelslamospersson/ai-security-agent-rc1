"""
Command service — orchestrates the Remote Command lifecycle.
"""

from __future__ import annotations

from typing import Any

import structlog

from management_server.commands.authorization import CommandAuthorizer
from management_server.commands.exceptions import (
    CommandNotFoundError,
)
from management_server.commands.lifecycle import CommandLifecycle
from management_server.commands.metrics import CommandMetricsCollector
from management_server.commands.models import (
    CommandPriority,
    CommandState,
    RemoteCommand,
)
from management_server.commands.queue import CommandQueue
from management_server.commands.repository import CommandRepository
from management_server.commands.schemas import (
    CommandSchema,
    CommandTypeInfo,
    CreateCommandRequest,
)
from management_server.commands.serializer import CommandSerializer
from management_server.commands.validator import CommandValidator

logger = structlog.get_logger("commands.service")


class CommandService:
    """Remote Command Framework service."""

    def __init__(
        self,
        repository: CommandRepository,
        queue: CommandQueue | None = None,
        authorizer: CommandAuthorizer | None = None,
        metrics: CommandMetricsCollector | None = None,
    ) -> None:
        self._repository = repository
        self._queue = queue or CommandQueue()
        self._authorizer = authorizer or CommandAuthorizer()
        self._metrics = metrics or CommandMetricsCollector()

    async def create_command(self, request: CreateCommandRequest) -> CommandSchema:
        """Create a new remote command."""
        CommandValidator.validate_and_raise(
            machine_id=request.machine_id,
            command_type=request.command_type,
            parameters=request.parameters,
            priority=request.priority,
        )

        command = RemoteCommand.create(
            machine_id=request.machine_id,
            command_type=request.command_type,
            parameters=request.parameters,
            priority=CommandPriority(request.priority),
            correlation_id=request.correlation_id,
            requested_by=request.requested_by,
            ttl_hours=request.ttl_hours,
        )

        await self._repository.create_command(command)
        self._metrics.command_created()

        # Auto-transition to QUEUED
        await self._transition(command.command_id, CommandState.QUEUED)

        # Enqueue
        await self._queue.enqueue(command)

        logger.info(
            "Command created",
            command_id=command.command_id,
            command_type=command.command_type,
            machine_id=command.machine_id,
        )

        return self._to_schema(command)

    async def authorize_command(
        self,
        command_id: str,
        authorized_by: str = "admin",
        reason: str = "",
    ) -> CommandSchema:
        """Authorize a queued command."""
        command = await self._get_command(command_id)
        current_state = CommandState(command["state"])

        CommandLifecycle.validate(current_state, CommandState.AUTHORIZED)

        updated = await self._repository.update_state(
            command_id,
            CommandState.AUTHORIZED,
            triggered_by=authorized_by,
            reason=reason,
        )
        self._metrics.command_authorized()

        # Auto-transition to READY
        await self._repository.update_state(
            command_id, CommandState.READY, triggered_by=authorized_by
        )

        logger.info("Command authorized", command_id=command_id, by=authorized_by)
        return CommandSchema(
            command_id=updated.get("command_id", ""),
            correlation_id=updated.get("correlation_id", ""),
            machine_id=updated.get("machine_id", ""),
            command_type=updated.get("command_type", ""),
            state=CommandState.READY.value,
        )

    async def cancel_command(
        self,
        command_id: str,
        cancelled_by: str = "admin",
        reason: str = "",
    ) -> CommandSchema:
        """Cancel a command."""
        command = await self._get_command(command_id)
        current_state = CommandState(command["state"])

        CommandLifecycle.validate(current_state, CommandState.CANCELLED)

        updated = await self._repository.update_state(
            command_id,
            CommandState.CANCELLED,
            triggered_by=cancelled_by,
            reason=reason,
        )
        self._metrics.command_cancelled()

        logger.info("Command cancelled", command_id=command_id, by=cancelled_by)
        return self._record_to_schema(updated)

    async def get_command(self, command_id: str) -> CommandSchema | None:
        """Get a command by ID."""
        record = await self._repository.get_command(command_id)
        if record is None:
            return None
        return self._record_to_schema(record)

    async def list_commands(
        self,
        limit: int = 100,
        offset: int = 0,
        machine_id: str | None = None,
        state: str | None = None,
    ) -> dict[str, Any]:
        """List commands with filters."""
        records, total = await self._repository.list_commands(
            limit=limit,
            offset=offset,
            machine_id=machine_id,
            state=state,
        )
        commands = [self._record_to_schema(r) for r in records]
        return {"commands": commands, "total": total}

    async def get_pending_for_machine(self, machine_id: str) -> list[dict[str, Any]]:
        """Get pending commands for a machine (for heartbeat delivery)."""
        records = await self._repository.get_pending_for_machine(machine_id)
        commands: list[RemoteCommand] = []
        for r in records:
            commands.append(
                RemoteCommand(
                    command_id=r.get("command_id", ""),
                    correlation_id=r.get("correlation_id", ""),
                    machine_id=r.get("machine_id", ""),
                    command_type=r.get("command_type", ""),
                    parameters={},
                    priority=CommandPriority.NORMAL,
                    state=CommandState(r.get("state", "created")),
                )
            )
        result: list[dict[str, Any]] = CommandSerializer.serialize_pending(commands)
        return result

    async def get_lifecycle(self, command_id: str) -> list[dict[str, Any]]:
        """Get lifecycle records for a command."""
        result: list[dict[str, Any]] = await self._repository.get_lifecycle(command_id)
        return result

    async def get_supported_types(self) -> list[CommandTypeInfo]:
        """Get all supported command types."""
        types = CommandValidator.get_supported_types()
        return [CommandTypeInfo(**t) for t in types]

    async def get_metrics(self) -> dict[str, int | float]:
        """Get command metrics."""
        total = await self._repository.count_commands()
        counts = await self._repository.count_by_state()
        queue_depth = self._queue.total_pending
        snap = self._metrics.snapshot(queue_depth=queue_depth)
        result_metrics: dict[str, Any] = {
            "commands_created": total,
            "commands_authorized": snap.commands_authorized,
            "commands_denied": snap.commands_denied,
            "commands_delivered": snap.commands_delivered,
            "commands_acknowledged": snap.commands_acknowledged,
            "commands_expired": snap.commands_expired,
            "commands_cancelled": snap.commands_cancelled,
            "authorization_failures": snap.authorization_failures,
            "queue_depth": queue_depth,
        }
        for k, v in counts.items():
            result_metrics[f"state_{k}"] = v
        return result_metrics

    async def _get_command(self, command_id: str) -> dict[str, Any]:
        record = await self._repository.get_command(command_id)
        if record is None:
            raise CommandNotFoundError(command_id)
        record_result: dict[str, Any] = record
        return record_result

    async def _transition(
        self,
        command_id: str,
        to_state: CommandState,
        triggered_by: str = "system",
        reason: str = "",
    ) -> dict[str, Any]:
        record = await self._repository.get_command(command_id)
        if record is None:
            raise CommandNotFoundError(command_id)
        current = CommandState(record["state"])
        CommandLifecycle.validate(current, to_state)
        transition_result: dict[str, Any] = await self._repository.update_state(
            command_id,
            to_state,
            triggered_by,
            reason,
        )
        return transition_result

    @staticmethod
    def _to_schema(command: RemoteCommand) -> CommandSchema:
        return CommandSchema(
            command_id=command.command_id,
            correlation_id=command.correlation_id,
            machine_id=command.machine_id,
            command_type=command.command_type,
            parameters=dict(command.parameters),
            priority=command.priority.value,
            state=command.state.value,
            created_at=command.created_at,
            expires_at=command.expires_at,
            requested_by=command.requested_by,
        )

    @staticmethod
    def _record_to_schema(record: dict[str, Any]) -> CommandSchema:
        import json

        params = {}
        if record.get("parameters_json"):
            try:
                params = json.loads(record["parameters_json"])
            except (json.JSONDecodeError, TypeError):
                params = {}
        return CommandSchema(
            command_id=record.get("command_id", ""),
            correlation_id=record.get("correlation_id", ""),
            machine_id=record.get("machine_id", ""),
            command_type=record.get("command_type", ""),
            parameters=params,
            priority=record.get("priority", "normal"),
            state=record.get("state", "created"),
            created_at=record.get("created_at"),
            expires_at=record.get("expires_at"),
            requested_by=record.get("requested_by", "system"),
        )
