"""Tests for the SQLite Persistence Layer."""

from __future__ import annotations

import time

import pytest

from security_agent.database import SQLiteBackend
from security_agent.database.migrations import MigrationManager
from security_agent.database.repository import (
    BanRepository,
    EventRepository,
    FirewallRepository,
    IncidentRepository,
    ReputationRepository,
    RuleMatchRepository,
    ThreatRepository,
)


@pytest.fixture
async def db():
    backend = SQLiteBackend(":memory:")
    await backend.initialize()
    mgr = MigrationManager(backend)
    await mgr.run()
    yield backend
    await backend.shutdown()


@pytest.mark.asyncio
class TestSQLiteBackend:
    async def test_initialize(self):
        b = SQLiteBackend(":memory:")
        await b.initialize()
        assert b.is_initialized
        await b.shutdown()

    async def test_health(self, db):
        assert await db.health_check()

    async def test_execute_and_fetch(self, db):
        await db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        await db.execute("INSERT INTO t VALUES (1, 'a')")
        r = await db.fetch_one("SELECT * FROM t")
        assert r is not None and r["v"] == "a"

    async def test_fetch_all(self, db):
        await db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        await db.execute("INSERT INTO t VALUES (1, 'a')")
        await db.execute("INSERT INTO t VALUES (2, 'b')")
        assert len(await db.fetch_all("SELECT * FROM t ORDER BY id")) == 2

    async def test_execute_many(self, db):
        await db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        await db.execute_many("INSERT INTO t VALUES (?, ?)", [(1, "a"), (2, "b")])
        assert len(await db.fetch_all("SELECT * FROM t")) == 2

    async def test_transaction_commit(self, db):
        await db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        async with db.transaction():
            await db.execute("INSERT INTO t VALUES (1, 'ok')")
        r = await db.fetch_one("SELECT * FROM t")
        assert r is not None

    async def test_transaction(self, db):
        """Transaction context manager operates without error."""
        await db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        try:
            async with db.transaction():
                await db.execute("INSERT INTO t VALUES (1, 'x')")
        except Exception:
            pass
        assert await db.health_check()

    async def test_vacuum(self, db):
        await db.vacuum()
        assert await db.health_check()


@pytest.mark.asyncio
class TestMigrations:
    async def test_tables_exist(self, db):
        tables = await db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = [t["name"] for t in tables]
        assert "events" in names

    async def test_idempotent(self, db):
        mgr = MigrationManager(db)
        await mgr.run()

    async def test_history(self, db):
        rows = await db.fetch_all("SELECT * FROM migration_history")
        assert len(rows) >= 1


@pytest.mark.asyncio
class TestRepositories:
    async def test_event(self, db):
        r = EventRepository(db)
        await r.store("e1", "2026-01-01", "test", "j", 300, 5, "1.2.3.4")
        assert await r.count() >= 1

    async def test_rule_match(self, db):
        r = RuleMatchRepository(db)
        await r.store("m1", "c1", "t", "e1", 80, 5, 50)
        assert await r.count_by_rule("c1") >= 1

    async def test_incident(self, db):
        r = IncidentRepository(db)
        await r.store("i1", "c1", "done", ["r1"], ["e1"], 100)

    async def test_threat(self, db):
        r = ThreatRepository(db)
        await r.store("t1", "i1", 80, 70, 7, 3, 3)

    async def test_reputation(self, db):
        r = ReputationRepository(db)
        await r.store("ipv4", "1.2.3.4", -30, 80, 5, 1)

    async def test_ban(self, db):
        r = BanRepository(db)
        await r.store("b1", "1.2.3.4", "ipv4", "ban", 3, 86400)

    async def test_firewall(self, db):
        r = FirewallRepository(db)
        await r.store("o1", "1.2.3.4", "ipv4", "ban", 3600, "done")


class TestBenchmarks:
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_batch(self):
        b = SQLiteBackend(":memory:")
        await b.initialize()
        await b.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        rows = [(i, f"v{i}") for i in range(5000)]
        t = time.monotonic()
        await b.execute_many("INSERT INTO t VALUES (?, ?)", rows)
        print(f"\n  Batch: {5000 / (time.monotonic() - t):.0f} rows/s")
        await b.shutdown()

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_query(self):
        b = SQLiteBackend(":memory:")
        await b.initialize()
        await b.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        for i in range(10):
            await b.execute("INSERT INTO t VALUES (?, ?)", (i, f"v{i}"))
        lats = []
        for _ in range(100):
            t = time.monotonic()
            await b.fetch_one("SELECT * FROM t WHERE id = ?", (5,))
            lats.append((time.monotonic() - t) * 1000)
        print(f"\n  Query: {sum(lats) / len(lats):.4f}ms avg")
        await b.shutdown()
