"""
Command validator — validates command existence, parameters, priority, and expiry.
"""

from __future__ import annotations

from typing import Any

import structlog

from management_server.commands.exceptions import (
    CommandValidationError,
)
from management_server.commands.models import (
    COMMAND_PARAMETER_SCHEMAS,
    CommandPriority,
    CommandType,
    RemoteCommand,
)

logger = structlog.get_logger("commands.validator")


class CommandValidator:
    """Validates commands before creation and queueing."""

    @staticmethod
    def validate_new(
        machine_id: str,
        command_type: str,
        parameters: dict[str, Any] | None = None,
        priority: str = "normal",
    ) -> list[str]:
        """Validate a new command request. Returns list of errors."""
        errors: list[str] = []

        if not machine_id:
            errors.append("machine_id is required")

        if not command_type:
            errors.append("command_type is required")
        elif command_type not in CommandType._value2member_map_:
            errors.append(f"Unknown command type: '{command_type}'")

        # Validate parameters against schema
        params = parameters or {}
        schema = COMMAND_PARAMETER_SCHEMAS.get(command_type, {})
        param_schemas = schema.get("parameters", {})

        for key, value in params.items():
            if key not in param_schemas:
                errors.append(f"Unknown parameter: '{key}' for command type '{command_type}'")
                continue
            expected_type = param_schemas[key].get("type", "string")
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"Parameter '{key}' must be a string")
            elif expected_type == "bool" and not isinstance(value, bool):
                errors.append(f"Parameter '{key}' must be a boolean")
            elif expected_type == "int" and not isinstance(value, int):
                errors.append(f"Parameter '{key}' must be an integer")
            elif expected_type == "float" and not isinstance(value, (int, float)):
                errors.append(f"Parameter '{key}' must be a number")

        # Validate priority
        valid_priorities = {p.value for p in CommandPriority}
        if priority not in valid_priorities:
            errors.append(f"Invalid priority: '{priority}'")

        return errors

    @staticmethod
    def validate_and_raise(
        machine_id: str,
        command_type: str,
        parameters: dict[str, Any] | None = None,
        priority: str = "normal",
    ) -> None:
        """Validate and raise on first error."""
        errors = CommandValidator.validate_new(machine_id, command_type, parameters, priority)
        if errors:
            raise CommandValidationError(errors[0])

    @staticmethod
    def validate_expiry(command: RemoteCommand) -> None:
        """Check if a command has expired."""
        if command.is_expired:
            raise CommandValidationError(f"Command {command.command_id} has expired")

    @staticmethod
    def get_supported_types() -> list[dict[str, Any]]:
        """Get all supported command types with their parameter schemas."""
        from management_server.commands.models import COMMAND_PARAMETER_SCHEMAS

        result: list[dict[str, Any]] = []
        for cmd_type in CommandType:
            schema = COMMAND_PARAMETER_SCHEMAS.get(cmd_type.value, {})
            result.append(
                {
                    "name": cmd_type.value,
                    "description": schema.get("description", ""),
                    "parameters": schema.get("parameters", {}),
                }
            )
        return result
