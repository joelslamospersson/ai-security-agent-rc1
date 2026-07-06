"""
Heartbeat exceptions — typed error hierarchy for the heartbeat protocol.
"""

from __future__ import annotations


class HeartbeatError(Exception):
    """Base exception for all heartbeat-related errors."""


class ProtocolMismatchError(HeartbeatError):
    """Agent and server protocol versions are incompatible."""

    def __init__(self, agent_version: int, server_version: int) -> None:
        self.agent_version = agent_version
        self.server_version = server_version
        super().__init__(
            f"Protocol version mismatch: agent v{agent_version}, server v{server_version}"
        )


class CapabilityError(HeartbeatError):
    """Capability advertisement or detection error."""


class MachineOfflineError(HeartbeatError):
    """Machine is offline and cannot accept commands."""

    def __init__(self, machine_uuid: str) -> None:
        self.machine_uuid = machine_uuid
        super().__init__(f"Machine {machine_uuid} is offline")


class HeartbeatValidationError(HeartbeatError):
    """Heartbeat payload failed validation."""


class HeartbeatRepositoryError(HeartbeatError):
    """Database error during heartbeat operations."""


class SequenceReplayError(HeartbeatError):
    """Heartbeat sequence number indicates replay or out-of-order delivery."""

    def __init__(self, expected: int, received: int) -> None:
        self.expected = expected
        self.received = received
        super().__init__(f"Sequence number mismatch: expected {expected}, received {received}")


class MachineNotRegisteredError(HeartbeatError):
    """Machine is not registered in the registry."""

    def __init__(self, machine_uuid: str) -> None:
        self.machine_uuid = machine_uuid
        super().__init__(f"Machine {machine_uuid} is not registered")
