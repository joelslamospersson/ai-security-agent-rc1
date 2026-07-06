"""
Heartbeat validator — validates heartbeat payloads and machine state.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from management_server.heartbeat.exceptions import (
    HeartbeatValidationError,
    MachineNotRegisteredError,
    ProtocolMismatchError,
    SequenceReplayError,
)
from management_server.heartbeat.models import ProtocolVersion
from management_server.heartbeat.schemas import HeartbeatRequestSchema

logger = structlog.get_logger("heartbeat.validator")

MAX_SEQUENCE_GAP = 1000  # Allow up to 1000 missed heartbeats before rejecting


class HeartbeatValidator:
    """Validates incoming heartbeat payloads."""

    @staticmethod
    def validate_request(schema: HeartbeatRequestSchema) -> None:
        """Validate the heartbeat request schema fields."""
        if not schema.machine_uuid:
            raise HeartbeatValidationError("machine_uuid is required")
        if not schema.protocol_version:
            raise HeartbeatValidationError("protocol_version is required")
        if schema.sequence_number < 0:
            raise HeartbeatValidationError("sequence_number must be non-negative")

    @staticmethod
    def validate_protocol_version(protocol_version: str) -> str:
        """Validate and negotiate the protocol version.

        Returns the negotiated version or raises ProtocolMismatchError.
        """
        if not protocol_version:
            raise ProtocolMismatchError(0, 1)
        if not ProtocolVersion.is_supported(protocol_version):
            latest = ProtocolVersion.latest().value
            logger.warning(
                "Unsupported protocol version, negotiating",
                agent_version=protocol_version,
                negotiated=latest,
            )
            result: str = latest
            return result
        return protocol_version

    @staticmethod
    def validate_sequence_number(
        last_sequence: int | None,
        current_sequence: int,
    ) -> None:
        """Validate heartbeat sequence number for replay protection.

        Args:
            last_sequence: The last sequence number from this machine.
            current_sequence: The sequence number in the current heartbeat.

        Raises:
            SequenceReplayError if the sequence is invalid.
        """
        if last_sequence is None:
            return  # First heartbeat, no prior sequence

        if current_sequence <= last_sequence:
            raise SequenceReplayError(last_sequence + 1, current_sequence)

        if current_sequence > last_sequence + MAX_SEQUENCE_GAP:
            logger.warning(
                "Large sequence gap detected",
                last_sequence=last_sequence,
                current_sequence=current_sequence,
            )

    @staticmethod
    def validate_machine_registered(machine_uuid: str, is_registered: bool) -> None:
        """Validate that the machine is registered."""
        if not is_registered:
            raise MachineNotRegisteredError(machine_uuid)

    @staticmethod
    def validate_timestamp_freshness(
        agent_timestamp: datetime | None,
        max_skew_seconds: int = 300,
    ) -> None:
        """Validate that the agent timestamp is not too far in the past or future."""
        if agent_timestamp is None:
            return
        now = datetime.now(tz=UTC)
        skew = abs((now - agent_timestamp).total_seconds())
        if skew > max_skew_seconds:
            logger.warning(
                "Large clock skew detected",
                skew_seconds=round(skew, 1),
                max_skew=max_skew_seconds,
            )
