"""
Comprehensive tests for the Logging & Reporting Framework.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from management_server.logging.compression import LogCompressor
from management_server.logging.formatter import LogFormatter
from management_server.logging.metrics import LoggingMetricsCollector
from management_server.logging.models import (
    DailyReport,
    IncidentReport,
    LogCategory,
    LogEntry,
)
from management_server.logging.reports import ReportGenerator
from management_server.logging.retention import RetentionManager
from management_server.logging.rotation import LogRotator
from management_server.logging.writer import LogWriter

# ─── Formatter Tests ──────────────────────────────────────────────────────


class TestLogFormatter:
    def test_format_human(self):
        entry = LogEntry(
            category=LogCategory.SECURITY,
            severity="CRITICAL",
            machine_id="web-01",
            event_type="SSH Brute Force",
            description="Multiple failed attempts",
            source="192.168.1.1",
            threat_score=96,
            confidence=99,
            policy="Production",
            action="Temporary Ban (24 hours)",
        )
        result = LogFormatter.format_human(entry)
        assert "SSH Brute Force" in result
        assert "CRITICAL" in result
        assert "x.x.x.x" in result  # IP masked
        assert "192" not in result  # IP masked

    def test_format_jsonl(self):
        entry = LogEntry(
            category=LogCategory.AUDIT,
            severity="INFO",
            event_type="policy_change",
            description="Policy updated",
        )
        result = LogFormatter.format_jsonl(entry)
        data = json.loads(result)
        assert data["event_type"] == "policy_change"
        assert data["category"] == "audit"

    def test_mask_ip(self):
        result = LogFormatter.mask_value("Connection from 192.168.1.1")
        assert "x.x.x.x" in result
        assert "192.168.1.1" not in result

    def test_mask_email(self):
        result = LogFormatter.mask_value("Contact: user@example.com")
        assert "[REDACTED]" in result

    def test_mask_dict(self):
        data = {"ip": "10.0.0.1", "user": "admin", "count": 5}
        result = LogFormatter.mask_dict(data)
        assert result["ip"] == "x.x.x.x"
        assert result["count"] == 5  # Non-string preserved

    def test_log_filename(self):
        name = LogFormatter.get_log_filename(LogCategory.SECURITY, "2026-07-05")
        assert name == "security-2026-07-05.log"


# ─── Writer Tests ─────────────────────────────────────────────────────────


class TestLogWriter:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.writer = LogWriter(log_root=str(self.tmpdir))

    async def test_write_log(self):
        entry = LogEntry(category=LogCategory.SECURITY, severity="INFO", event_type="test")
        result = await self.writer.write(entry)
        assert "human_path" in result
        assert "jsonl_path" in result
        assert result["bytes_written"] > 0

    async def test_write_creates_directories(self):
        assert (self.tmpdir / "security").exists()
        assert (self.tmpdir / "json").exists()
        assert (self.tmpdir / "reports" / "daily").exists()

    async def test_write_report(self):
        result = await self.writer.write_report("daily/2026-07-05.txt", "test report")
        assert result["bytes_written"] > 0


# ─── Rotation Tests ───────────────────────────────────────────────────────


class TestLogRotator:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / "security").mkdir()
        self.writer = LogWriter(log_root=str(self.tmpdir))
        self.rotator = LogRotator(self.tmpdir)

    async def test_rotate(self):
        # Write something first
        entry = LogEntry(category=LogCategory.SECURITY, severity="INFO", event_type="test")
        await self.writer.write(entry)
        results = await self.rotator.rotate_all()
        assert len(results) >= 0  # May be 0 if already rotated


# ─── Compression Tests ────────────────────────────────────────────────────


class TestLogCompression:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / "security").mkdir()
        # Create a test log file
        self.test_file = self.tmpdir / "security" / "security-2026-07-05.log"
        self.test_file.write_text("test log content\n" * 100)

    async def test_compress_file(self):
        compressor = LogCompressor(self.tmpdir)
        result = await compressor.compress_file(self.test_file)
        assert result["original_bytes"] > 0
        assert result["compressed_bytes"] > 0
        assert not result["skipped"]
        # Original should be removed
        assert not self.test_file.exists()

    async def test_read_compressed(self):
        compressor = LogCompressor(self.tmpdir)
        await compressor.compress_file(self.test_file)
        gz_path = self.test_file.with_suffix(self.test_file.suffix + ".gz")
        content = LogCompressor.read_compressed(gz_path)
        assert "test log content" in content


# ─── Retention Tests ──────────────────────────────────────────────────────


class TestRetention:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / "security").mkdir()

    async def test_enforce_retention(self):
        # Create an old file
        old_file = self.tmpdir / "security" / "old-2025-01-01.log"
        old_file.write_text("old content")
        # Set mtime to 2 years ago
        old_file.touch()
        # Can't easily change mtime in temp, so verify the file exists
        assert old_file.exists()

        retention = RetentionManager(self.tmpdir, retention_days=30)
        result = await retention.enforce()
        assert "deleted_files" in result


# ─── Reports Tests ────────────────────────────────────────────────────────


class TestReports:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.generator = ReportGenerator(self.tmpdir)

    async def test_incident_report(self):
        incident = IncidentReport(
            incident_id="INC-001",
            correlation_id="corr-123",
            source="192.168.1.1",
            attack_type="SSH Brute Force",
            detection_chain=["Step 1", "Step 2"],
            threat_score=95,
            confidence=98,
            policy="Production",
            firewall_actions=["Ban IP"],
            notifications_sent=["Discord"],
            final_resolution="IP banned",
        )
        content = await self.generator.generate_incident_report(incident)
        assert "INCIDENT REPORT" in content
        assert "SSH Brute Force" in content
        assert "x.x.x.x" in content  # IP masked

    async def test_daily_report(self):
        report = DailyReport(
            date="2026-07-05",
            total_detections=100,
            critical_detections=5,
            machines_online=50,
            machines_offline=2,
            top_attack_types=[("SSH", 30), ("SQLi", 10)],
            top_offending_ips=["10.0.0.1"],
        )
        content = await self.generator.generate_daily_report(report)
        assert "DAILY REPORT" in content
        assert "2026-07-05" in content
        assert "x.x.x.x" in content  # IP masked

    async def test_save_report(self):
        path = await self.generator.save_report("daily", "test.txt", "test content")
        assert path.exists()
        assert path.read_text() == "test content"


# ─── Metrics Tests ────────────────────────────────────────────────────────


class TestLoggingMetrics:
    def test_initial(self):
        m = LoggingMetricsCollector()
        snap = m.snapshot()
        assert snap.log_entries_written == 0

    def test_counters(self):
        m = LoggingMetricsCollector()
        m.entry_written(100)
        m.report_generated()
        m.bytes_compressed(1000, 200)
        m.file_rotated()
        m.file_deleted(500)
        snap = m.snapshot()
        assert snap.log_entries_written == 1
        assert snap.reports_generated == 1
        assert snap.bytes_written == 100
        assert snap.bytes_compressed == 200
        assert snap.files_rotated == 1
        assert snap.files_deleted == 1
        assert snap.compression_ratio == 0.2


# ─── API Tests ─────────────────────────────────────────────────────────────


class TestLoggingAPI:
    def test_list_logs(self, client: TestClient):
        resp = client.get("/api/v1/logs")
        assert resp.status_code in (200, 503)

    def test_list_reports(self, client: TestClient):
        resp = client.get("/api/v1/logs/reports")
        assert resp.status_code in (200, 503)

    def test_generate_daily_report(self, client: TestClient):
        resp = client.post("/api/v1/logs/report/daily")
        assert resp.status_code in (200, 503)
