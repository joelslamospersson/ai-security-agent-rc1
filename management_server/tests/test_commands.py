"""
Comprehensive tests for the Remote Command Framework.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.commands.authorization import CommandAuthorizer
from management_server.commands.exceptions import (
    InvalidTransitionError,
)
from management_server.commands.lifecycle import CommandLifecycle
from management_server.commands.metrics import CommandMetricsCollector
from management_server.commands.models import (
    COMMAND_PARAMETER_SCHEMAS,
    CommandState,
    CommandType,
    RemoteCommand,
)
from management_server.commands.queue import CommandQueue
from management_server.commands.repository import CommandRepository
from management_server.commands.serializer import CommandSerializer
from management_server.commands.service import CommandService
from management_server.commands.validator import CommandValidator

# ─── Model Tests ──────────────────────────────────────────────────────────


class TestRemoteCommand:
    def test_create(self):
        cmd = RemoteCommand.create(
            machine_id="m-001",
            command_type="restart_agent",
            parameters={"force": True},
        )
        assert cmd.command_id != ""
        assert cmd.state == CommandState.CREATED
        assert cmd.command_type == "restart_agent"
        assert cmd.parameters["force"] is True

    def test_frozen(self):
        cmd = RemoteCommand.create("m-001", "restart_agent")
        with pytest.raises(AttributeError):
            cmd.command_id = "changed"  # type: ignore[misc]

    def test_expired(self):
        past = datetime.now(tz=UTC) - timedelta(hours=1)
        cmd = RemoteCommand(expires_at=past)
        assert cmd.is_expired

    def test_not_expired(self):
        future = datetime.now(tz=UTC) + timedelta(hours=1)
        cmd = RemoteCommand(expires_at=future)
        assert not cmd.is_expired


class TestCommandType:
    def test_all_types_have_schemas(self):
        for cmd_type in CommandType:
            assert cmd_type.value in COMMAND_PARAMETER_SCHEMAS

    def test_all_types_are_supported(self):
        types = CommandValidator.get_supported_types()
        assert len(types) >= 12


# ─── Lifecycle Tests ──────────────────────────────────────────────────────


class TestCommandLifecycle:
    def test_legal_transitions(self):
        assert CommandLifecycle.is_legal(CommandState.CREATED, CommandState.QUEUED)
        assert CommandLifecycle.is_legal(CommandState.QUEUED, CommandState.AUTHORIZED)

    def test_illegal_transitions(self):
        assert not CommandLifecycle.is_legal(CommandState.CREATED, CommandState.SUCCESS)
        assert not CommandLifecycle.is_legal(CommandState.DELIVERED, CommandState.CREATED)

    def test_validate_raises(self):
        with pytest.raises(InvalidTransitionError):
            CommandLifecycle.validate(CommandState.CREATED, CommandState.SUCCESS)

    def test_can_cancel(self):
        assert CommandLifecycle.can_cancel(CommandState.CREATED)
        assert CommandLifecycle.can_cancel(CommandState.QUEUED)
        assert not CommandLifecycle.can_cancel(CommandState.RUNNING)

    def test_legal_transitions_from_created(self):
        targets = CommandLifecycle.legal_transitions_from(CommandState.CREATED)
        assert CommandState.QUEUED in targets
        assert CommandState.CANCELLED in targets
        assert CommandState.EXPIRED in targets

    def test_full_lifecycle(self):
        transitions = [
            (CommandState.CREATED, CommandState.QUEUED),
            (CommandState.QUEUED, CommandState.AUTHORIZED),
            (CommandState.AUTHORIZED, CommandState.READY),
            (CommandState.READY, CommandState.DELIVERED),
            (CommandState.DELIVERED, CommandState.ACKNOWLEDGED),
            (CommandState.ACKNOWLEDGED, CommandState.RUNNING),
            (CommandState.RUNNING, CommandState.SUCCESS),
        ]
        for from_s, to_s in transitions:
            assert CommandLifecycle.is_legal(from_s, to_s), f"{from_s} -> {to_s} should be legal"


# ─── Validator Tests ──────────────────────────────────────────────────────


class TestCommandValidator:
    def test_valid_command(self):
        errors = CommandValidator.validate_new(
            machine_id="m-001",
            command_type="restart_agent",
            parameters={"force": True},
        )
        assert len(errors) == 0

    def test_missing_machine_id(self):
        errors = CommandValidator.validate_new(machine_id="", command_type="restart_agent")
        assert any("machine_id" in e for e in errors)

    def test_unknown_command_type(self):
        errors = CommandValidator.validate_new(machine_id="m-001", command_type="unknown_type")
        assert any("Unknown command type" in e for e in errors)

    def test_unknown_parameter(self):
        errors = CommandValidator.validate_new(
            machine_id="m-001",
            command_type="restart_agent",
            parameters={"unknown_param": "value"},
        )
        assert any("Unknown parameter" in e for e in errors)

    def test_wrong_parameter_type(self):
        errors = CommandValidator.validate_new(
            machine_id="m-001",
            command_type="collect_diagnostics",
            parameters={"include_logs": "not_a_bool"},
        )
        assert any("boolean" in e for e in errors)

    def test_invalid_priority(self):
        errors = CommandValidator.validate_new(
            machine_id="m-001",
            command_type="restart_agent",
            priority="urgent",
        )
        assert any("Invalid priority" in e for e in errors)


# ─── Authorization Tests ──────────────────────────────────────────────────


class TestCommandAuthorizer:
    async def test_authorized(self):
        cmd = RemoteCommand.create("m-001", "restart_agent")
        authorizer = CommandAuthorizer()
        result = await authorizer.authorize(cmd)
        assert result.authorized

    async def test_deny_unregistered(self):
        cmd = RemoteCommand.create("m-001", "restart_agent")
        authorizer = CommandAuthorizer()
        result = await authorizer.authorize(cmd, is_machine_registered=False)
        assert not result.authorized
        assert result.stage == "machine_registration"

    async def test_deny_by_policy(self):
        cmd = RemoteCommand.create("m-001", "restart_agent")
        authorizer = CommandAuthorizer()
        result = await authorizer.authorize(cmd, denied_commands=["restart_agent"])
        assert not result.authorized
        assert result.stage == "policy"

    async def test_deny_not_allowed(self):
        cmd = RemoteCommand.create("m-001", "restart_agent")
        authorizer = CommandAuthorizer()
        result = await authorizer.authorize(cmd, allowed_commands=["reload_configuration"])
        assert not result.authorized

    async def test_deny_feature_flag(self):
        cmd = RemoteCommand.create("m-001", "maintenance_enable")
        authorizer = CommandAuthorizer()
        result = await authorizer.authorize(cmd, feature_flags={"maintenance_mode": False})
        assert not result.authorized
        assert result.stage == "feature_flag"


# ─── Serializer Tests ─────────────────────────────────────────────────────


class TestCommandSerializer:
    def test_serialize(self):
        cmd = RemoteCommand.create("m-001", "restart_agent", parameters={"force": True})
        data = CommandSerializer.serialize(cmd)
        assert data["command_id"] == cmd.command_id
        assert data["command_type"] == "restart_agent"
        assert data["version"] == "1.0"

    def test_deserialize(self):
        cmd = RemoteCommand.create("m-001", "restart_agent")
        data = CommandSerializer.serialize(cmd)
        restored = CommandSerializer.deserialize(data)
        assert restored.command_id == cmd.command_id
        assert restored.command_type == cmd.command_type

    def test_serialize_pending(self):
        ready = RemoteCommand.create("m-001", "restart_agent")
        # Override state to READY
        ready = RemoteCommand(
            command_id=ready.command_id,
            machine_id=ready.machine_id,
            command_type=ready.command_type,
            state=CommandState.READY,
        )
        pending = CommandSerializer.serialize_pending([ready])
        assert len(pending) == 1


# ─── Queue Tests ──────────────────────────────────────────────────────────


class TestCommandQueue:
    async def test_enqueue_dequeue(self):
        q = CommandQueue()
        cmd = RemoteCommand.create("m-001", "restart_agent")
        await q.enqueue(cmd)
        assert q.total_enqueued == 1
        dequeued = q.dequeue_nowait("normal")
        assert dequeued is not None
        assert dequeued.command_id == cmd.command_id

    async def test_queue_depth(self):
        q = CommandQueue()
        for _i in range(3):
            cmd = RemoteCommand.create("m-001", "restart_agent")
            await q.enqueue(cmd)
        depth = q.depth()
        assert isinstance(depth, dict)
        assert depth.get("normal", 0) == 3


# ─── Metrics Tests ────────────────────────────────────────────────────────


class TestCommandMetrics:
    def test_initial(self):
        m = CommandMetricsCollector()
        snap = m.snapshot()
        assert snap.commands_created == 0

    def test_counters(self):
        m = CommandMetricsCollector()
        m.command_created()
        m.command_authorized()
        m.command_denied()
        m.command_delivered()
        snap = m.snapshot(queue_depth=2)
        assert snap.commands_created == 1
        assert snap.commands_authorized == 1
        assert snap.queue_depth == 2


# ─── Repository Tests ─────────────────────────────────────────────────────


class TestCommandRepository:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = CommandRepository(sqlite_session)
        self.session = sqlite_session

    async def test_create_and_get(self):
        cmd = RemoteCommand.create("m-001", "restart_agent")
        await self.repo.create_command(cmd)
        got = await self.repo.get_command(cmd.command_id)
        assert got is not None
        assert got["command_type"] == "restart_agent"

    async def test_update_state(self):
        cmd = RemoteCommand.create("m-001", "restart_agent")
        await self.repo.create_command(cmd)
        updated = await self.repo.update_state(cmd.command_id, CommandState.QUEUED)
        assert updated["state"] == "queued"

    async def test_get_pending_for_machine(self):
        cmd = RemoteCommand.create("m-001", "restart_agent")
        await self.repo.create_command(cmd)
        await self.repo.update_state(cmd.command_id, CommandState.AUTHORIZED)
        pending = await self.repo.get_pending_for_machine("m-001")
        assert len(pending) >= 1

    async def test_list_commands(self):
        for _i in range(3):
            cmd = RemoteCommand.create("m-list", "restart_agent")
            await self.repo.create_command(cmd)
        _records, total = await self.repo.list_commands()
        assert total >= 3


# ─── Service Tests ────────────────────────────────────────────────────────


class TestCommandService:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = CommandRepository(sqlite_session)
        self.service = CommandService(repository=self.repo)

    async def test_create(self):
        from management_server.commands.schemas import CreateCommandRequest

        req = CreateCommandRequest(machine_id="m-001", command_type="restart_agent")
        schema = await self.service.create_command(req)
        assert schema.command_id != ""
        assert schema.command_type == "restart_agent"

    async def test_authorize(self):
        from management_server.commands.schemas import CreateCommandRequest

        req = CreateCommandRequest(machine_id="m-001", command_type="restart_agent")
        schema = await self.service.create_command(req)
        auth = await self.service.authorize_command(schema.command_id)
        assert auth.state == "ready"

    async def test_cancel(self):
        from management_server.commands.schemas import CreateCommandRequest

        req = CreateCommandRequest(machine_id="m-001", command_type="restart_agent")
        schema = await self.service.create_command(req)
        cancelled = await self.service.cancel_command(schema.command_id)
        assert cancelled.state == "cancelled"

    async def test_get_command_not_found(self):
        result = await self.service.get_command("nonexistent")
        assert result is None

    async def test_list_commands(self):
        from management_server.commands.schemas import CreateCommandRequest

        req = CreateCommandRequest(machine_id="m-001", command_type="restart_agent")
        await self.service.create_command(req)
        result = await self.service.list_commands()
        assert result["total"] >= 1

    async def test_supported_types(self):
        types = await self.service.get_supported_types()
        assert len(types) >= 12

    async def test_get_metrics(self):
        metrics = await self.service.get_metrics()
        assert "commands_created" in metrics


# ─── API Tests ─────────────────────────────────────────────────────────────


class TestCommandAPI:
    def test_list_commands_no_db(self, client: TestClient):
        resp = client.get("/api/v1/commands")
        assert resp.status_code in (503,)

    def test_create_command_no_db(self, client: TestClient):
        resp = client.post(
            "/api/v1/commands",
            json={"machine_id": "m-001", "command_type": "restart_agent"},
        )
        assert resp.status_code in (503,)

    def test_get_types_no_db(self, client: TestClient):
        resp = client.get("/api/v1/commands/types")
        assert resp.status_code in (503,)
