"""
Tests for startup initialization, dialect support, and migration manager.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from management_server.database.dialect import (
    DatabaseDialect,
    detect_dialect,
    dialect_to_migration_dir,
)
from management_server.database.migrations import _discover_migration_files, run_migrations
from management_server.startup.models import InitState, StartupReport, SubsystemStatus
from management_server.startup.report import print_startup_report


class TestDialectDetection:
    def test_detect_postgres(self):
        assert detect_dialect("postgresql+asyncpg://localhost/db") == DatabaseDialect.POSTGRESQL

    def test_detect_sqlite(self):
        assert detect_dialect("sqlite+aiosqlite:///dev.db") == DatabaseDialect.SQLITE

    def test_detect_unknown(self):
        assert detect_dialect("mysql://localhost/db") == DatabaseDialect.UNKNOWN

    def test_migration_dir_postgres(self):
        assert dialect_to_migration_dir(DatabaseDialect.POSTGRESQL) == "postgres"

    def test_migration_dir_sqlite(self):
        assert dialect_to_migration_dir(DatabaseDialect.SQLITE) == "sqlite"


class TestMigrationFiles:
    def test_postgres_migrations_exist(self):
        files = _discover_migration_files(DatabaseDialect.POSTGRESQL)
        assert len(files) >= 1
        assert all(f.name.endswith(".sql") for f in files)

    def test_sqlite_migrations_exist(self):
        files = _discover_migration_files(DatabaseDialect.SQLITE)
        assert len(files) >= 1
        assert all(f.name.endswith(".sql") for f in files)


class TestMigrationExecution:
    async def test_sqlite_migration_runs(self):
        """Verify SQLite migration SQL is valid."""
        engine = create_async_engine("sqlite+aiosqlite://", echo=False)
        async with engine.begin() as conn:
            await run_migrations(conn, DatabaseDialect.SQLITE)
            result = await conn.execute(text("SELECT COUNT(*) FROM migration_history"))
            count = result.scalar()
            assert count is not None
        await engine.dispose()


class TestStartupReport:
    def test_report_initial_state(self):
        report = StartupReport()
        assert report.aborted is False
        assert len(report.stages) == 0

    def test_set_state(self):
        report = StartupReport()
        report.stages["database"] = SubsystemStatus(name="database", state=InitState.PENDING)
        report.set_state("database", InitState.READY)
        assert report.stages["database"].state == InitState.READY

    def test_all_ready(self):
        report = StartupReport()
        for name in ["db", "cache", "queue"]:
            report.stages[name] = SubsystemStatus(name=name, state=InitState.READY)
        assert report.all_ready

    def test_any_failed(self):
        report = StartupReport()
        report.stages["db"] = SubsystemStatus(name="db", state=InitState.FAILED)
        assert report.any_failed

    def test_to_dict(self):
        report = StartupReport()
        report.stages["test"] = SubsystemStatus(name="test", state=InitState.READY)
        d = report.to_dict()
        assert "stages" in d
        assert d["stages"]["test"]["state"] == "ready"

    def test_print_report(self, capsys):
        report = StartupReport()
        report.stages["configuration"] = SubsystemStatus(
            name="configuration",
            state=InitState.READY,
        )
        report.stages["database"] = SubsystemStatus(
            name="database",
            state=InitState.FAILED,
            error="connection refused",
        )
        print_startup_report(report)
        captured = capsys.readouterr()
        assert "READY" in captured.out or "OK" in captured.out
        assert "FAILED" in captured.out or "connection refused" in captured.out


class TestHealthEndpoint:
    def test_health_endpoint(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "application" in data
