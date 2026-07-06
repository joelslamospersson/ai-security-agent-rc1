"""
Command authorization — four-stage validation pipeline.

1. Machine Registered
2. Certificate Valid
3. Policy Allows Command
4. Feature Flag Enabled
"""

from __future__ import annotations

from typing import Any

import structlog

from management_server.commands.models import CommandPriority, RemoteCommand

logger = structlog.get_logger("commands.authorization")


class AuthorizationResult:
    """Result of an authorization check."""

    def __init__(self) -> None:
        self.authorized: bool = True
        self.stage: str = ""
        self.reason: str = ""

    def deny(self, stage: str, reason: str) -> None:
        self.authorized = False
        self.stage = stage
        self.reason = reason


class CommandAuthorizer:
    """Four-stage authorization pipeline for remote commands."""

    def __init__(self) -> None:
        self._checks: list[tuple[str, Any]] = []

    async def authorize(
        self,
        command: RemoteCommand,
        is_machine_registered: bool = True,
        is_certificate_valid: bool = True,
        allowed_commands: list[str] | None = None,
        denied_commands: list[str] | None = None,
        feature_flags: dict[str, bool] | None = None,
    ) -> AuthorizationResult:
        """Run all authorization stages. Returns result."""
        result = AuthorizationResult()

        # Stage 1: Machine Registration
        if not is_machine_registered:
            result.deny("machine_registration", f"Machine {command.machine_id} is not registered")
            return result

        # Stage 2: Certificate Validity
        if not is_certificate_valid:
            result.deny("certificate_validity", "Machine certificate is invalid or expired")
            return result

        # Stage 3: Policy allow/deny
        allowed = allowed_commands or []
        denied = denied_commands or []

        if command.command_type in denied:
            result.deny("policy", f"Command '{command.command_type}' is denied by policy")
            return result

        if allowed and command.command_type not in allowed:
            result.deny("policy", f"Command '{command.command_type}' is not allowed by policy")
            return result

        # Stage 4: Feature flags
        ff = feature_flags or {}
        required_ff_map: dict[str, str] = {
            "maintenance_enable": "maintenance_mode",
            "maintenance_disable": "maintenance_mode",
        }
        required_ff = required_ff_map.get(command.command_type)
        if required_ff and not ff.get(required_ff, False):
            result.deny("feature_flag", f"Feature flag '{required_ff}' is not enabled")
            return result

        result.authorized = True
        return result

    @staticmethod
    def check_priority(command: RemoteCommand, max_priority: str = "immediate") -> bool:
        """Check if a command's priority is within allowed range."""
        priority_order = {
            CommandPriority.IMMEDIATE: 4,
            CommandPriority.HIGH: 3,
            CommandPriority.NORMAL: 2,
            CommandPriority.LOW: 1,
        }
        max_order = priority_order.get(CommandPriority(max_priority), 4)
        cmd_order = priority_order.get(command.priority, 2)
        return cmd_order <= max_order
