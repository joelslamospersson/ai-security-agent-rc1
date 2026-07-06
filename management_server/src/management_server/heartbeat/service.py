"""
Heartbeat service — orchestrates heartbeat processing, timeout detection,
status tracking, and capability management.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog

from management_server.heartbeat.exceptions import (
    HeartbeatError,
    HeartbeatValidationError,
    MachineNotRegisteredError,
    ProtocolMismatchError,
    SequenceReplayError,
)
from management_server.heartbeat.metrics import HeartbeatMetricsCollector
from management_server.heartbeat.models import (
    HeartbeatRequest,
    MachineStatus,
    TimeoutConfig,
)
from management_server.heartbeat.protocol import HeartbeatProtocol
from management_server.heartbeat.repository import HeartbeatRepository
from management_server.heartbeat.schemas import (
    HeartbeatMetricsSchema,
    HeartbeatRequestSchema,
    HeartbeatResponseSchema,
    MachineStatusSchema,
)
from management_server.heartbeat.validator import HeartbeatValidator

logger = structlog.get_logger("heartbeat.service")


class HeartbeatService:
    """Heartbeat and management protocol service."""

    def __init__(
        self,
        repository: HeartbeatRepository,
        protocol: HeartbeatProtocol | None = None,
        metrics: HeartbeatMetricsCollector | None = None,
        timeout_config: TimeoutConfig | None = None,
    ) -> None:
        self._repository = repository
        self._protocol = protocol or HeartbeatProtocol()
        self._metrics = metrics or HeartbeatMetricsCollector()
        self._timeout_config = timeout_config or TimeoutConfig()

    async def process_heartbeat(
        self,
        schema: HeartbeatRequestSchema,
        is_machine_registered: bool = True,
    ) -> HeartbeatResponseSchema:
        """Process an incoming heartbeat from an agent.

        This is the main entry point for the heartbeat protocol.
        It validates, negotiates, records, and responds.
        """
        start = datetime.now(tz=UTC)

        try:
            # 1. Validate request
            HeartbeatValidator.validate_request(schema)

            # 2. Check machine is registered
            HeartbeatValidator.validate_machine_registered(
                schema.machine_uuid, is_machine_registered
            )

            # 3. Negotiate protocol version
            try:
                negotiated = HeartbeatValidator.validate_protocol_version(schema.protocol_version)
            except ProtocolMismatchError:
                self._metrics.version_mismatch()
                self._metrics.protocol_error()
                raise

            if negotiated != schema.protocol_version:
                self._metrics.version_mismatch()

            # 4. Validate sequence number
            last_seq = await self._repository.get_last_sequence_number(schema.machine_uuid)
            try:
                HeartbeatValidator.validate_sequence_number(last_seq, schema.sequence_number)
            except SequenceReplayError:
                self._metrics.protocol_error()
                raise

            # 5. Parse the request
            request = self._protocol.parse_request(schema)

            # 6. Detect capability changes
            cap_changes = await self._detect_capability_changes(schema.machine_uuid, request)

            # 7. Record heartbeat
            health_json = json.dumps(request.health.__dict__) if request.health else ""
            caps_json = json.dumps(request.capabilities.__dict__) if request.capabilities else ""
            queues_json = json.dumps(request.queues.__dict__) if request.queues else ""
            security_json = json.dumps(request.security.__dict__) if request.security else ""

            await self._repository.record_heartbeat(
                machine_uuid=schema.machine_uuid,
                protocol_version=negotiated,
                agent_version=schema.agent_version,
                hostname=schema.hostname,
                environment=schema.environment,
                sequence_number=schema.sequence_number,
                health_json=health_json,
                capabilities_json=caps_json,
                queues_json=queues_json,
                security_json=security_json,
                status=MachineStatus.HEALTHY,
            )

            # 8. Record capability changes
            for change in cap_changes:
                await self._repository.record_capability_change(
                    machine_uuid=schema.machine_uuid,
                    capability=change["capability"],
                    change_type=change["change"],
                    old_value=change.get("old_value"),
                    new_value=change.get("new_value"),
                )
                self._metrics.capability_change()

            # 9. Build response
            response = self._protocol.build_response(
                _request=request,
                negotiated_version=negotiated,
            )

            self._metrics.heartbeat_received()

            elapsed = (datetime.now(tz=UTC) - start).total_seconds() * 1000
            logger.info(
                "Heartbeat processed",
                machine_uuid=schema.machine_uuid,
                negotiated_version=negotiated,
                sequence=schema.sequence_number,
                latency_ms=round(elapsed, 2),
            )

            return HeartbeatResponseSchema(
                acknowledged=True,
                negotiated_version=negotiated,
                server_timestamp=response.server_timestamp,
            )

        except (
            HeartbeatValidationError,
            MachineNotRegisteredError,
            ProtocolMismatchError,
            SequenceReplayError,
        ) as e:
            self._metrics.protocol_error()
            logger.warning(
                "Heartbeat rejected",
                machine_uuid=schema.machine_uuid,
                error=str(e),
            )
            raise

        except Exception as e:
            self._metrics.protocol_error()
            logger.error(
                "Heartbeat processing failed",
                machine_uuid=schema.machine_uuid,
                error=str(e),
            )
            raise HeartbeatError(f"Heartbeat processing failed: {e}") from e

    async def detect_timeouts(self) -> list[dict[str, Any]]:
        """Detect machines that have timed out and update their status.

        Returns a list of status changes.
        """
        db_changes: list[dict[str, Any]] = await self._repository.detect_offline_machines(
            self._timeout_config
        )
        for change in db_changes:
            self._metrics.heartbeat_missed()
            logger.info(
                "Machine status changed due to timeout",
                machine_uuid=change["machine_uuid"],
                from_status=change["old_status"],
                to_status=change["new_status"],
            )
        result_list: list[dict[str, Any]] = await self._repository.detect_offline_machines(
            self._timeout_config
        )
        return result_list

    async def get_machine_status(self, machine_uuid: str) -> MachineStatusSchema:
        """Get the current status of a machine."""
        record = await self._repository.get_machine_status(machine_uuid)
        if record is None:
            return MachineStatusSchema(
                machine_uuid=machine_uuid,
                status=MachineStatus.UNKNOWN.value,
            )
        caps_json = record.get("capabilities_json") or ""
        caps: list[str] = []
        if caps_json:
            try:
                caps_data = json.loads(caps_json)
                if isinstance(caps_data, dict):
                    caps = [k for k, v in caps_data.items() if v]
            except json.JSONDecodeError:
                pass

        return MachineStatusSchema(
            machine_uuid=machine_uuid,
            status=record.get("status", MachineStatus.UNKNOWN.value),
            hostname=record.get("hostname", ""),
            protocol_version=record.get("protocol_version", ""),
            agent_version=record.get("agent_version", ""),
            last_heartbeat=record.get("last_heartbeat_at"),
            environment=record.get("environment", ""),
            capabilities=caps,
        )

    async def get_metrics(self) -> HeartbeatMetricsSchema:
        """Get heartbeat metrics snapshot."""
        counts = await self._repository.get_status_counts()
        _total_hb = await self._repository.get_heartbeat_count()
        online = counts.get("healthy", 0)
        offline = counts.get("offline", 0)
        delayed = counts.get("delayed", 0)
        snapshot = self._metrics.snapshot(online=online, offline=offline, delayed=delayed)
        return HeartbeatMetricsSchema(
            heartbeats_received=snapshot.heartbeats_received,
            heartbeats_missed=snapshot.heartbeats_missed,
            protocol_errors=snapshot.protocol_errors,
            version_mismatches=snapshot.version_mismatches,
            capability_changes=snapshot.capability_changes,
            average_latency_ms=snapshot.average_latency_ms,
            online_machines=online,
            offline_machines=offline,
            delayed_machines=delayed,
        )

    async def _detect_capability_changes(
        self,
        machine_uuid: str,
        request: HeartbeatRequest,
    ) -> list[dict[str, Any]]:
        """Detect changes between old and new capabilities."""
        if request.capabilities is None:
            return []

        old_caps_json = await self._repository.get_latest_capabilities_json(machine_uuid)
        old_caps: dict[str, bool] = {}
        if old_caps_json:
            try:
                old_caps = json.loads(old_caps_json)
            except (json.JSONDecodeError, TypeError):
                old_caps = {}

        new_caps = request.capabilities.__dict__
        # Extract only the boolean capability fields
        new_caps_bool = {
            k: v for k, v in new_caps.items() if isinstance(v, bool) and k != "feature_flags"
        }

        cap_changes: list[dict[str, Any]] = self._protocol.detect_capability_changes(
            old_caps, new_caps_bool
        )
        return cap_changes
