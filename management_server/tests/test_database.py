"""
Tests for the Management Server database layer.

Uses SQLite for model tests. PostgreSQL integration tests require a running
PostgreSQL instance and are skipped otherwise.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from management_server.config.settings import Settings
from management_server.database.base import Base, TimestampedModel
from management_server.database.exceptions import ConnectionError, MigrationError, TransactionError
from management_server.database.models import MigrationHistory, SchemaVersion
from management_server.database.repositories import MigrationRepository
from management_server.database.session import create_engine as make_engine


@pytest.fixture
async def sqlite_engine():
    """Create an in-memory SQLite engine for model tests."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def sqlite_session(sqlite_engine):
    """Create an async session against the SQLite engine."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(sqlite_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


class TestBaseModel:
    def test_base_imports(self):
        assert Base is not None
        assert TimestampedModel is not None

    async def test_model_creation(self, sqlite_session: AsyncSession):
        """Verify models can be created and persisted."""
        mh = MigrationHistory(version=1, name="test", checksum="abc", success=True)
        sqlite_session.add(mh)
        await sqlite_session.commit()

        result = await sqlite_session.execute(
            text("SELECT version, name FROM migration_history WHERE version = 1")
        )
        row = result.fetchone()
        assert row is not None
        assert row.version == 1
        assert row.name == "test"


class TestSettings:
    def test_database_url_property(self):
        settings = Settings(
            db_user="test", db_password="pass", db_host="localhost", db_database="testdb"
        )
        url = settings.database_url
        assert "postgresql+asyncpg://" in url
        assert "test:pass" in url
        assert "localhost" in url
        assert "testdb" in url

    def test_database_url_sync(self):
        settings = Settings(
            db_user="test", db_password="pass", db_host="localhost", db_database="testdb"
        )
        url = settings.database_url_sync
        assert "postgresql://" in url
        assert "asyncpg" not in url


class TestModels:
    async def test_migration_history_table(self, sqlite_session: AsyncSession):
        mh = MigrationHistory(version=1, name="001_test", checksum="sha256:abc", success=True)
        sqlite_session.add(mh)
        await sqlite_session.commit()

        result = await sqlite_session.execute(
            text("SELECT version, name, checksum FROM migration_history WHERE version = 1")
        )
        row = result.fetchone()
        assert row is not None
        assert row.version == 1
        assert row.name == "001_test"

    async def test_schema_version_table(self, sqlite_session: AsyncSession):
        sv = SchemaVersion(version=0)
        sqlite_session.add(sv)
        await sqlite_session.commit()

        result = await sqlite_session.execute(text("SELECT version FROM schema_version"))
        row = result.fetchone()
        assert row is not None
        assert row.version == 0


class TestRepository:
    async def test_migration_repository(self, sqlite_session: AsyncSession):
        repo = MigrationRepository(sqlite_session)

        # No versions yet
        version = await repo.get_current_version()
        assert version is None

        # Add a version
        await sqlite_session.execute(text("INSERT INTO schema_version (version) VALUES (1)"))
        await sqlite_session.commit()

        version = await repo.get_current_version()
        assert version == 1


class TestExceptions:
    def test_database_error(self):
        with pytest.raises(ConnectionError):
            raise ConnectionError("test connection error")

    def test_migration_error(self):
        with pytest.raises(MigrationError):
            raise MigrationError("test migration error")

    def test_transaction_error(self):
        with pytest.raises(TransactionError):
            raise TransactionError("test transaction error")


class TestHealthEndpoint:
    def test_health_without_db(self):
        """Health endpoint should work without database connection."""
        from management_server.app import create_app
        from management_server.config.settings import Settings

        app = create_app(Settings(debug=True))
        from fastapi.testclient import TestClient

        with TestClient(app) as c:
            response = c.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "database" in data
            assert data["database"]["connected"] is False
            assert data["status"] in ("degraded", "failed")


class TestSession:
    async def test_engine_creation(self):
        """Engine creation with settings should not raise."""
        try:
            settings = Settings(
                db_user="test", db_password="test", db_host="localhost", db_database="test"
            )
            engine = make_engine(settings)
            assert engine is not None
            await engine.dispose()
        except Exception as e:
            if "asyncpg" in str(e):
                pytest.skip("asyncpg not installed")
            raise

    async def test_session_factory(self):
        """Session factory function should be importable and usable."""
        from management_server.database.session import create_session_factory

        try:
            settings = Settings(db_user="u", db_password="p", db_host="localhost", db_database="d")
            engine = make_engine(settings)
            factory = create_session_factory(engine)
            assert factory is not None
            await engine.dispose()
        except Exception as e:
            if "asyncpg" in str(e):
                pytest.skip("asyncpg not installed")
            raise
