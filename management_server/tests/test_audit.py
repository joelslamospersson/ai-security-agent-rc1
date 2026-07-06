"""
Comprehensive tests for the Audit Engine subsystem.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.audit.event import AuditEventFactory
from management_server.audit.exporter import CsvExporter, ExportRegistry, JsonExporter
from management_server.audit.metrics import AuditMetricsCollector
from management_server.audit.models import (
    AuditEvent,
    AuditOutcome,
    AuditSeverity,
    RetentionPolicy,
)
from management_server.audit.repository import AuditRepository
from management_server.audit.retention import RetentionCalculator
from management_server.audit.service import AuditService
from management_server.audit.validator import AuditValidator

# ─── AuditEvent Tests ─────────────────────────────────────────────────────


class TestAuditEvent:
    def test_create(self):
        event = AuditEvent.create(
            subsystem="system",
            event_type="test",
            description="Test event",
        )
        assert event.audit_id != ""
        assert event.current_hash != ""
        assert event.previous_hash == ""
        assert event.verify_integrity()

    def test_frozen(self):
        event = AuditEvent.create("system", "test")
        with pytest.raises(AttributeError):
            event.audit_id = "changed"  # type: ignore[misc]

    def test_hash_chaining(self):
        e1 = AuditEvent.create("system", "event1")
        e2 = AuditEvent.create("system", "event2", previous_hash=e1.current_hash)
        assert e2.previous_hash == e1.current_hash
        assert e1.current_hash != e2.current_hash

    def test_tamper_detection(self):
        event = AuditEvent.create("system", "test", description="Original")
        assert event.verify_integrity()
        # Create a modified version
        tampered = AuditEvent(
            audit_id=event.audit_id,
            subsystem=event.subsystem,
            event_type=event.event_type,
            description="MODIFIED",
            current_hash=event.current_hash,
            previous_hash=event.previous_hash,
        )
        assert not tampered.verify_integrity()

    def test_hash_determinism(self):
        e1 = AuditEvent.create("system", "test", metadata={"key": "value"})
        # Same content should produce same hash
        content = (
            f"{e1.audit_id}|{e1.correlation_id}|{e1.timestamp.isoformat()}|{e1.machine_id}|"
            f"{e1.subsystem}|{e1.actor}|{e1.event_type}|{e1.severity.value}|{e1.outcome.value}|"
            f"{e1.description}|{e1.metadata_json}|{e1.previous_hash}"
        )
        import hashlib

        assert e1.current_hash == hashlib.sha256(content.encode()).hexdigest()

    def test_factory_success(self):
        event = AuditEventFactory.success("system", "test", "All good")
        assert event.severity == AuditSeverity.INFO
        assert event.outcome == AuditOutcome.SUCCESS

    def test_factory_failure(self):
        event = AuditEventFactory.failure("system", "test", "Something failed")
        assert event.severity == AuditSeverity.ERROR
        assert event.outcome == AuditOutcome.FAILURE


# ─── Validator Tests ──────────────────────────────────────────────────────


class TestAuditValidator:
    def test_valid_event(self):
        event = AuditEvent.create("system", "test")
        errors = AuditValidator.validate(event)
        assert len(errors) == 0

    def test_missing_subsystem(self):
        event = AuditEvent(subsystem="", event_type="test")
        errors = AuditValidator.validate(event)
        assert any("subsystem" in e for e in errors)

    def test_unknown_subsystem(self):
        event = AuditEvent.create("unknown_subsystem", "test")
        errors = AuditValidator.validate(event)
        assert any("Unknown subsystem" in e for e in errors)

    def test_chain_verification(self):
        e1 = AuditEvent.create("system", "e1")
        e2 = AuditEvent.create("system", "e2", previous_hash=e1.current_hash)
        valid, _failed = AuditValidator.verify_chain([e1, e2])
        assert valid

    def test_chain_verification_failure(self):
        e1 = AuditEvent.create("system", "e1")
        e2 = AuditEvent.create("system", "e2", previous_hash="wrong_hash")
        valid, _failed = AuditValidator.verify_chain([e1, e2])
        assert not valid


# ─── Retention Tests ──────────────────────────────────────────────────────


class TestRetention:
    def test_retention_policy_default(self):
        p = RetentionPolicy()
        assert p.retention_days == 365
        assert p.max_records == 1_000_000

    def test_should_retain(self):
        p = RetentionPolicy(retention_days=30)
        old = datetime.now(tz=UTC) - timedelta(days=60)
        recent = datetime.now(tz=UTC) - timedelta(days=1)
        assert not p.should_retain(old)
        assert p.should_retain(recent)

    def test_retention_analysis(self):
        calc = RetentionCalculator()
        report = calc.analyze(total_events=1000)
        assert report.total_events == 1000


# ─── Exporter Tests ───────────────────────────────────────────────────────


class TestExporters:
    def test_json_export(self):
        exporter = JsonExporter()
        events = [{"audit_id": "1", "event_type": "test"}]
        filename, data = exporter.export(events)
        assert filename.endswith(".json")
        assert len(data) > 0

    def test_csv_export(self):
        exporter = CsvExporter()
        events = [{"audit_id": "1", "event_type": "test"}]
        filename, data = exporter.export(events)
        assert filename.endswith(".csv")
        assert b"audit_id" in data

    def test_registry(self):
        r = ExportRegistry()
        assert r.get("json") is not None
        assert r.get("csv") is not None


# ─── Metrics Tests ────────────────────────────────────────────────────────


class TestAuditMetrics:
    def test_initial(self):
        m = AuditMetricsCollector()
        snap = m.snapshot()
        assert snap.events_written == 0

    def test_counters(self):
        m = AuditMetricsCollector()
        m.event_written()
        m.validation_failure()
        m.export_requested()
        m.hash_failure()
        m.retention_calculated()
        snap = m.snapshot()
        assert snap.events_written == 1
        assert snap.validation_failures == 1
        assert snap.export_requests == 1
        assert snap.hash_failures == 1
        assert snap.retention_calculations == 1


# ─── Repository Tests ─────────────────────────────────────────────────────


class TestAuditRepository:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = AuditRepository(sqlite_session)
        self.session = sqlite_session

    async def test_append_and_get(self):
        event = AuditEvent.create("system", "test")
        result = await self.repo.append(event)
        assert result["audit_id"] == event.audit_id

        got = await self.repo.get(event.audit_id)
        assert got is not None
        assert got["event_type"] == "test"

    async def test_get_last(self):
        e1 = AuditEvent.create("system", "e1")
        await self.repo.append(e1)
        e2 = AuditEvent.create("system", "e2", previous_hash=e1.current_hash)
        await self.repo.append(e2)

        last = await self.repo.get_last()
        assert last is not None
        assert last["event_type"] == "e2"

    async def test_get_ordered(self):
        for i in range(3):
            e = AuditEvent.create("system", f"event_{i}")
            await self.repo.append(e)
        _rows, total = await self.repo.get_ordered()
        assert total >= 3

    async def test_get_ordered_filtered(self):
        e = AuditEvent.create("certificates", "cert_issue")
        await self.repo.append(e)
        _rows, total = await self.repo.get_ordered(subsystem="certificates")
        assert total >= 1

    async def test_count_events(self):
        count = await self.repo.count_events()
        initial = count
        e = AuditEvent.create("system", "count_test")
        await self.repo.append(e)
        count = await self.repo.count_events()
        assert count == initial + 1


# ─── Service Tests ────────────────────────────────────────────────────────


class TestAuditService:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = AuditRepository(sqlite_session)
        self.service = AuditService(repository=self.repo)

    async def test_record(self):
        schema = await self.service.record(
            subsystem="system",
            event_type="test_event",
            description="Test recording",
        )
        assert schema.audit_id != ""
        assert schema.current_hash != ""

    async def test_record_with_chaining(self):
        s1 = await self.service.record("system", "event1")
        s2 = await self.service.record("system", "event2")
        assert s2.previous_hash == s1.current_hash

    async def test_get_event(self):
        schema = await self.service.record("system", "get_test")
        got = await self.service.get_event(schema.audit_id)
        assert got is not None
        assert got.event_type == "get_test"

    async def test_list_events(self):
        await self.service.record("system", "list_test")
        result = await self.service.list_events()
        assert result["total"] >= 1

    async def test_integrity_verification(self):
        await self.service.record("system", "v1")
        await self.service.record("system", "v2")
        result = await self.service.verify_integrity()
        assert result.verified

    async def test_integrity_verification_empty(self):
        result = await self.service.verify_integrity()
        assert result.verified
        assert result.total_events == 0

    async def test_export_json(self):
        await self.service.record("system", "export_test")
        result = await self.service.export_events(format_name="json")
        assert result.format == "json"
        assert result.event_count >= 1

    async def test_retention_report(self):
        report = await self.service.get_retention_report()
        assert report.total_events >= 0

    async def test_get_metrics(self):
        metrics = await self.service.get_metrics()
        assert "events_written" in metrics


# ─── API Tests ─────────────────────────────────────────────────────────────


class TestAuditAPI:
    def test_list_audit_no_db(self, client: TestClient):
        resp = client.get("/api/v1/audit")
        assert resp.status_code in (503,)

    def test_get_audit_no_db(self, client: TestClient):
        resp = client.get("/api/v1/audit/test-id")
        assert resp.status_code in (503,)

    def test_verify_no_db(self, client: TestClient):
        resp = client.get("/api/v1/audit/verify")
        assert resp.status_code in (503,)

    def test_export_no_db(self, client: TestClient):
        resp = client.post("/api/v1/audit/export", json={"format": "json"})
        assert resp.status_code in (503,)
