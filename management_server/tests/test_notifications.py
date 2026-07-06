"""
Comprehensive tests for the Notification Engine subsystem.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.notifications.adapters import AdapterRegistry, ConsoleAdapter
from management_server.notifications.exceptions import (
    QueueError,
)
from management_server.notifications.formatter import (
    DiscordEmbedFormatter,
    FormatterRegistry,
    JsonFormatter,
    MarkdownFormatter,
    PlainTextFormatter,
)
from management_server.notifications.metrics import NotificationMetricsCollector
from management_server.notifications.models import (
    DeliveryResult,
    Notification,
    NotificationStatus,
)
from management_server.notifications.queue import NotificationQueue
from management_server.notifications.repository import NotificationRepository
from management_server.notifications.service import NotificationService
from management_server.notifications.validator import NotificationValidator

# ─── Notification Model Tests ─────────────────────────────────────────────


class TestNotification:
    def test_create(self):
        n = Notification.create(
            routing_decision_id="rd-1",
            machine_id="m1",
            event_type="test",
            destination="console",
        )
        assert n.notification_id != ""
        assert n.status == NotificationStatus.PENDING

    def test_frozen(self):
        n = Notification.create("rd-1", "m1", "test", "console")
        with pytest.raises(AttributeError):
            n.machine_id = "changed"  # type: ignore[misc]


class TestDeliveryResult:
    def test_success(self):
        r = DeliveryResult.success("nid-1", "console", 5.0)
        assert r.status.value == "success"
        assert r.latency_ms == 5.0

    def test_failure(self):
        r = DeliveryResult.failure("nid-1", "adapter", "ERR_001", "Failed")
        assert r.status.value == "failed"
        assert r.error_code == "ERR_001"


# ─── Formatter Tests ──────────────────────────────────────────────────────


class TestFormatters:
    def test_json_format(self):
        f = JsonFormatter()
        result = f.format("test", "m1", "console", "normal")
        assert "event_type" in result
        assert "machine_id" in result

    def test_markdown_format(self):
        f = MarkdownFormatter()
        result = f.format("critical_alert", "m1", "discord", "immediate")
        assert "# Notification:" in result
        assert "critical_alert" in result
        assert "immediate" in result

    def test_plain_text_format(self):
        f = PlainTextFormatter()
        result = f.format("heartbeat", "m1", "archive", "low")
        assert "Notification: heartbeat" in result

    def test_discord_embed_format(self):
        f = DiscordEmbedFormatter()
        result = f.format("test", "m1", "discord", "high")
        assert "embeds" in result
        assert "title" in result

    def test_registry_get(self):
        r = FormatterRegistry()
        assert r.get("json") is not None
        assert r.get("markdown") is not None
        assert r.get("nonexistent") is None

    def test_registry_get_or_default(self):
        r = FormatterRegistry()
        fmt = r.get_or_default("nonexistent")
        assert fmt is not None


# ─── Adapter Tests ────────────────────────────────────────────────────────


class TestAdapters:
    async def test_console_adapter(self):
        a = ConsoleAdapter()
        n = Notification.create("rd-1", "m1", "test", "console")
        result = await a.deliver(n)
        assert result.status.value == "success"
        assert result.adapter == "console"

    async def test_adapter_registry(self):
        r = AdapterRegistry()
        assert r.get("console") is not None
        assert r.get("archive") is not None
        # Unknown destinations fall back to noop
        adapter = r.get("nonexistent")
        assert adapter is not None


# ─── Validator Tests ──────────────────────────────────────────────────────


class TestNotificationValidator:
    def test_valid_notification(self):
        n = Notification.create("rd-1", "m1", "test", "console")
        v = NotificationValidator()
        errors = v.validate_notification(n)
        assert len(errors) == 0

    def test_missing_fields(self):
        n = Notification()
        v = NotificationValidator()
        errors = v.validate_notification(n)
        assert len(errors) >= 4  # id, routing_decision, machine, event_type

    def test_unknown_destination(self):
        n = Notification.create("rd-1", "m1", "test", "unknown_dest")
        v = NotificationValidator()
        errors = v.validate_notification(n)
        assert any("Unknown destination" in e for e in errors)


# ─── Queue Tests ──────────────────────────────────────────────────────────


class TestNotificationQueue:
    async def test_enqueue_dequeue(self):
        q = NotificationQueue()
        n = Notification.create("rd-1", "m1", "test", "console")
        await q.enqueue(n, "normal")
        assert q.total_enqueued == 1
        item = q.dequeue_nowait("normal")
        assert item is not None
        assert item.notification.notification_id == n.notification_id

    async def test_queue_depth(self):
        q = NotificationQueue()
        for i in range(3):
            n = Notification.create(f"rd-{i}", "m1", "test", "console")
            await q.enqueue(n, "high")

        depth = q.depth()
        assert isinstance(depth, dict)
        assert depth.get("high", 0) == 3

    async def test_invalid_priority_raises(self):
        q = NotificationQueue()
        n = Notification.create("rd-1", "m1", "test", "console")
        with pytest.raises(QueueError):
            await q.enqueue(n, "invalid_priority")

    async def test_empty_dequeue(self):
        q = NotificationQueue()
        item = q.dequeue_nowait("normal")
        assert item is None

    async def test_multiple_priorities(self):
        q = NotificationQueue()
        for pri in ["immediate", "high", "normal", "low", "bulk"]:
            n = Notification.create(f"rd-{pri}", "m1", "test", "console")
            await q.enqueue(n, pri)
        depths = q.depth()
        assert isinstance(depths, dict)
        for pri in ["immediate", "high", "normal", "low", "bulk"]:
            assert depths.get(pri, 0) == 1


# ─── Metrics Tests ────────────────────────────────────────────────────────


class TestNotificationMetrics:
    def test_initial(self):
        m = NotificationMetricsCollector()
        snap = m.snapshot()
        assert snap.notifications_created == 0

    def test_counters(self):
        m = NotificationMetricsCollector()
        m.notification_created()
        m.notification_queued()
        m.notification_dispatched()
        m.formatter_latency(5.0)
        m.delivery_attempt()
        m.skipped()
        snap = m.snapshot(queue_depth=3)
        assert snap.notifications_created == 1
        assert snap.notifications_queued == 1
        assert snap.notifications_dispatched == 1
        assert snap.formatter_latency_ms == 5.0
        assert snap.queue_depth == 3
        assert snap.delivery_attempts == 1
        assert snap.skipped_notifications == 1


# ─── Repository Tests ─────────────────────────────────────────────────────


class TestNotificationRepository:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = NotificationRepository(sqlite_session)
        self.session = sqlite_session

    async def test_save_and_get_notification(self):
        n = Notification.create("rd-1", "m1", "test", "console")
        await self.repo.save_notification(n)
        got = await self.repo.get_notification(n.notification_id)
        assert got is not None
        assert got["notification_id"] == n.notification_id

    async def test_list_notifications(self):
        for i in range(3):
            n = Notification.create(f"rd-{i}", "m1", "test", "console")
            await self.repo.save_notification(n)
        _rows, total = await self.repo.list_notifications()
        assert total >= 3

    async def test_update_status(self):
        n = Notification.create("rd-update", "m1", "test", "console")
        await self.repo.save_notification(n)
        await self.repo.update_status(n.notification_id, "dispatched")
        got = await self.repo.get_notification(n.notification_id)
        assert got["status"] == "dispatched"

    async def test_save_delivery_result(self):
        n = Notification.create("rd-dr", "m1", "test", "console")
        await self.repo.save_notification(n)
        await self.repo.save_delivery_result(n.notification_id, "success", "console", 5.0)
        results = await self.repo.get_delivery_results(n.notification_id)
        assert len(results) >= 1


# ─── Service Tests ────────────────────────────────────────────────────────


class TestNotificationService:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = NotificationRepository(sqlite_session)
        self.service = NotificationService(repository=self.repo)

    async def test_create_notification(self):
        schema = await self.service.create_notification(
            routing_decision_id="rd-svc-1",
            machine_id="svc-m1",
            event_type="test",
            destination="console",
        )
        assert schema.notification_id != ""
        assert schema.destination == "console"

    async def test_get_notification(self):
        schema = await self.service.create_notification("rd-svc-2", "svc-m2", "test", "console")
        got = await self.service.get_notification(schema.notification_id)
        assert got is not None

    async def test_list_notifications(self):
        await self.service.create_notification("rd-list", "m-list", "test", "console")
        result = await self.service.list_notifications()
        assert result["total"] >= 1

    async def test_preview(self):
        preview = await self.service.preview(
            event_type="test", destination="console", template="json"
        )
        assert preview.template == "json"
        assert preview.estimated_size_bytes > 0

    async def test_preview_markdown(self):
        preview = await self.service.preview(
            event_type="critical_alert", destination="discord", template="markdown"
        )
        assert preview.template == "markdown"

    async def test_replay(self):
        schemas = await self.service.replay("rd-replay", ["console", "archive"])
        assert len(schemas) == 2

    async def test_queue_and_dispatch(self):
        schema = await self.service.create_notification(
            "rd-dispatch", "m-dispatch", "test", "console"
        )
        await self.service.queue_notification(schema.notification_id)
        result = await self.service.dispatch(schema.notification_id)
        assert result.status.value in ("success", "failed")

    async def test_get_metrics(self):
        await self.service.create_notification("rd-metrics", "m-metrics", "test", "console")
        metrics = await self.service.get_metrics()
        assert "notifications_created" in metrics

    async def test_get_queue_depth(self):
        depth = await self.service.get_queue_depth()
        assert isinstance(depth, dict)


# ─── API Tests ─────────────────────────────────────────────────────────────


class TestNotificationAPI:
    def test_list_notifications_no_db(self, client: TestClient):
        resp = client.get("/api/v1/notifications")
        assert resp.status_code in (503,)

    def test_get_notification_no_db(self, client: TestClient):
        resp = client.get("/api/v1/notifications/test-id")
        assert resp.status_code in (503,)

    def test_queue_depth_no_db(self, client: TestClient):
        resp = client.get("/api/v1/notifications/queue")
        assert resp.status_code in (503,)

    def test_preview_no_db(self, client: TestClient):
        resp = client.post(
            "/api/v1/notifications/preview",
            json={"event_type": "test", "template": "json"},
        )
        assert resp.status_code in (503,)

    def test_replay_no_db(self, client: TestClient):
        resp = client.post(
            "/api/v1/notifications/replay",
            json={"routing_decision_id": "test-id"},
        )
        assert resp.status_code in (503,)
