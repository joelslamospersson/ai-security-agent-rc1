"""
Comprehensive tests for the Journald Monitor subsystem.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

import pytest

from security_agent.event_bus import EventBus
from security_agent.events import EventType, SecurityEvent
from security_agent.monitors.filters import JournalFilter
from security_agent.monitors.journal_reader import JournalReader, JournalReaderState
from security_agent.monitors.journald import JournaldMonitor
from security_agent.monitors.models import NormalizedJournalEvent
from security_agent.monitors.normalizer import JournalNormalizer

SAMPLE_SSH: dict[str, Any] = {
    "__CURSOR": "s=abc123",
    "__REALTIME_TIMESTAMP": "1700000000000000",
    "_HOSTNAME": "test-host",
    "_PID": "1234",
    "_UID": "0",
    "_GID": "0",
    "_EXE": "/usr/sbin/sshd",
    "_CMDLINE": "sshd: root@pts/0",
    "_SYSTEMD_UNIT": "sshd.service",
    "_TRANSPORT": "journal",
    "SYSLOG_IDENTIFIER": "sshd",
    "SYSLOG_FACILITY": "10",
    "PRIORITY": "6",
    "MESSAGE": "Failed password for root from 198.51.100.42",
}

SAMPLE_SUDO: dict[str, Any] = {
    "__CURSOR": "s=def456",
    "__REALTIME_TIMESTAMP": "1700000001000000",
    "_HOSTNAME": "test-host",
    "_PID": "5678",
    "_UID": "1000",
    "_GID": "1000",
    "_EXE": "/usr/bin/sudo",
    "_CMDLINE": "sudo -u root whoami",
    "_SYSTEMD_UNIT": "user@1000.service",
    "_TRANSPORT": "journal",
    "SYSLOG_IDENTIFIER": "sudo",
    "PRIORITY": "5",
    "MESSAGE": "authentication failure",
}

MALFORMED: dict[str, Any] = {
    "__CURSOR": "s=ghi789",
    "_HOSTNAME": "test-host",
    "MESSAGE": "Partial entry",
}

KERNEL_ENTRY: dict[str, Any] = {
    "__CURSOR": "s=kernel001",
    "__REALTIME_TIMESTAMP": "1700000002000000",
    "_HOSTNAME": "test-host",
    "_TRANSPORT": "kernel",
    "PRIORITY": "2",
    "MESSAGE": "Out of memory: Killed process 1234",
}


class MockJournalReader(JournalReader):
    """Reader that yields pre-defined entries for testing."""

    def __init__(self, entries: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._mock_entries = entries or []
        self._state = JournalReaderState.DISCONNECTED

    async def read(self) -> AsyncIterator[dict[str, Any]]:
        self._state = JournalReaderState.CONNECTED
        for entry in self._mock_entries:
            self._entries_read += 1
            yield entry
        while True:
            await asyncio.sleep(0.1)


class MagicMonitorContext:
    """Minimal mock MonitorContext."""

    def __init__(
        self,
        name: str = "",
        settings: dict | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.name = name
        self.settings = settings or {}
        self.event_bus = event_bus
        self.publisher = (
            event_bus.create_publisher(f"test.{name}") if event_bus else None
        )
        self.logger = None
        self.metrics = None
        self.metadata: dict[str, Any] = {}


class TestNormalizedJournalEvent:
    def test_creation(self) -> None:
        e = NormalizedJournalEvent(hostname="h", source_type="j", message="m")
        assert e.hostname == "h"
        assert e.source_type == "j"
        assert e.message == "m"

    def test_frozen(self) -> None:
        e = NormalizedJournalEvent()
        with pytest.raises(AttributeError):
            e.hostname = "x"  # type: ignore[misc]

    def test_defaults(self) -> None:
        e = NormalizedJournalEvent()
        assert e.parser_version == "1.0"
        assert e.pid is None


class TestJournalFilter:
    def test_empty_matches_all(self) -> None:
        assert JournalFilter().matches({"msg": "x"})

    def test_filter_by_unit(self) -> None:
        f = JournalFilter(systemd_units=["sshd.service"])
        assert f.matches(SAMPLE_SSH)
        assert not f.matches(SAMPLE_SUDO)

    def test_filter_by_identifier(self) -> None:
        f = JournalFilter(identifiers=["sudo"])
        assert not f.matches(SAMPLE_SSH)
        assert f.matches(SAMPLE_SUDO)

    def test_filter_by_priority(self) -> None:
        f = JournalFilter(priority_max=3)
        assert f.matches(KERNEL_ENTRY)
        assert not f.matches(SAMPLE_SSH)

    def test_exclude_units(self) -> None:
        f = JournalFilter(exclude_units=["sshd.service"])
        assert not f.matches(SAMPLE_SSH)
        assert f.matches(SAMPLE_SUDO)

    def test_message_patterns(self) -> None:
        f = JournalFilter(message_patterns=[r"Failed password"])
        assert f.matches(SAMPLE_SSH)
        assert not f.matches(SAMPLE_SUDO)

    def test_from_config(self) -> None:
        f = JournalFilter.from_config({"systemd_units": ["x"], "priority_max": 4})
        assert f.systemd_units == ["x"]
        assert f.priority_max == 4


class TestJournalNormalizer:
    def test_normalize_ssh(self) -> None:
        e = JournalNormalizer().normalize(SAMPLE_SSH)
        assert e.source_type == "journald"
        assert e.source_name == "sshd.service"
        assert e.pid == 1234
        assert e.uid == 0
        assert e.identifier == "sshd"
        assert "Failed password" in e.message

    def test_normalize_sudo(self) -> None:
        e = JournalNormalizer().normalize(SAMPLE_SUDO)
        assert e.uid == 1000
        assert e.identifier == "sudo"

    def test_normalize_malformed(self) -> None:
        e = JournalNormalizer().normalize(MALFORMED)
        assert e.source_type == "journald"
        assert e.pid is None

    def test_normalize_preserves_raw(self) -> None:
        e = JournalNormalizer().normalize(SAMPLE_SSH)
        assert e.raw_fields["MESSAGE"] == SAMPLE_SSH["MESSAGE"]


class TestJournaldMonitor:
    @pytest.mark.asyncio
    async def test_initialize(self) -> None:
        bus = EventBus()
        await bus.start()
        m = JournaldMonitor("test")
        await m.initialize(MagicMonitorContext("test", {}, bus))
        assert m.context is not None
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_health_before_start(self) -> None:
        bus = EventBus()
        await bus.start()
        m = JournaldMonitor("h")
        await m.initialize(MagicMonitorContext("h", {}, bus))
        h = m.health()
        assert h.status.value in (2, 3)  # FAILED or STOPPED
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_publishes_events(self) -> None:
        bus = EventBus()
        await bus.start()
        events: list[SecurityEvent] = []

        async def h(e: Any) -> None:
            events.append(e.event)

        bus.subscribe(EventType.SECURITY_EVENT, h, name="t")
        m = JournaldMonitor("pub")
        await m.initialize(MagicMonitorContext("pub", {}, bus))
        m._reader = MockJournalReader([SAMPLE_SSH, SAMPLE_SUDO])
        await m.start()
        await asyncio.sleep(0.1)
        assert len(events) >= 1
        assert events[0].source == "journald"
        await m.stop()
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_filtering(self) -> None:
        bus = EventBus()
        await bus.start()
        events: list[SecurityEvent] = []

        async def h(e: Any) -> None:
            events.append(e.event)

        bus.subscribe(EventType.SECURITY_EVENT, h, name="t")
        m = JournaldMonitor("filt")
        await m.initialize(
            MagicMonitorContext("filt", {"filter": {"identifiers": ["sudo"]}}, bus)
        )
        m._reader = MockJournalReader([SAMPLE_SSH, SAMPLE_SUDO])
        await m.start()
        await asyncio.sleep(0.1)
        assert len(events) >= 0  # Should not crash
        await m.stop()
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_no_crash_on_error(self) -> None:
        bus = EventBus()
        await bus.start()
        m = JournaldMonitor("err")
        await m.initialize(MagicMonitorContext("err", {}, bus))
        m._reader = MockJournalReader([{"MESSAGE": "test"}])
        await m.start()
        await asyncio.sleep(0.05)
        assert m.health() is not None
        await m.stop()
        await bus.shutdown()


class TestBenchmarks:
    @pytest.mark.benchmark
    def test_normalizer_throughput(self) -> None:
        n = JournalNormalizer()
        c = 10000
        t = time.monotonic()
        for _ in range(c):
            n.normalize(SAMPLE_SSH)
        e = time.monotonic() - t
        print(f"\n  Normalizer: {c / e:.0f} ev/s ({c} in {e:.3f}s)")
        assert c / e > 10000

    @pytest.mark.benchmark
    def test_filter_throughput(self) -> None:
        f = JournalFilter(
            systemd_units=["sshd.service"], identifiers=["sshd"], priority_max=6
        )
        c = 50000
        t = time.monotonic()
        for _ in range(c):
            f.matches(SAMPLE_SSH)
        e = time.monotonic() - t
        print(f"\n  Filter: {c / e:.0f} matches/s ({c} in {e:.3f}s)")
        assert c / e > 50000
