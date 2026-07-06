"""
Command serializer — serializes commands for heartbeat transport.

Supports protocol versioning, backward/forward compatibility.
The serializer is the protocol contract.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from management_server.commands.models import CommandPriority, CommandState, RemoteCommand

logger = structlog.get_logger("commands.serializer")

SERIALIZER_VERSION = "1.0"


class CommandSerializer:
    """Serializes and deserializes RemoteCommand objects for transport."""

    @staticmethod
    def serialize(command: RemoteCommand) -> dict[str, Any]:
        """Serialize a command for heartbeat response.

        Uses a versioned format for forward/backward compatibility.
        """
        return {
            "version": SERIALIZER_VERSION,
            "command_id": command.command_id,
            "correlation_id": command.correlation_id,
            "machine_id": command.machine_id,
            "command_type": command.command_type,
            "parameters": dict(command.parameters),
            "priority": command.priority.value,
            "state": command.state.value,
            "created_at": command.created_at.isoformat(),
            "expires_at": command.expires_at.isoformat(),
        }

    @staticmethod
    def serialize_pending(commands: list[RemoteCommand]) -> list[dict[str, Any]]:
        """Serialize all pending (READY) commands for heartbeat delivery."""
        return [
            CommandSerializer.serialize(cmd)
            for cmd in commands
            if cmd.state == CommandState.READY and not cmd.is_expired
        ]

    @staticmethod
    def deserialize(data: dict[str, Any]) -> RemoteCommand:
        """Deserialize a command from transport format.

        Tolerates unknown fields for forward compatibility.
        """
        try:
            created_at = data.get("created_at")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            expires_at = data.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
        except (ValueError, TypeError):
            now = datetime.now(tz=UTC)
            created_at = created_at or now
            expires_at = expires_at or now

        return RemoteCommand(
            command_id=str(data.get("command_id", "")),
            correlation_id=str(data.get("correlation_id", "")),
            machine_id=str(data.get("machine_id", "")),
            command_type=str(data.get("command_type", "")),
            parameters=dict(data.get("parameters", {})),
            priority=CommandPriority(str(data.get("priority", "normal"))),
            state=CommandState(str(data.get("state", "created"))),
            created_at=created_at or datetime.now(tz=UTC),
            expires_at=expires_at or datetime.now(tz=UTC),
        )

    @staticmethod
    def serialize_acknowledgement(
        command_id: str,
        machine_id: str,
        status: str = "acknowledged",
    ) -> dict[str, Any]:
        """Serialize a command acknowledgement from the agent."""
        return {
            "version": SERIALIZER_VERSION,
            "command_id": command_id,
            "machine_id": machine_id,
            "status": status,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
