"""JournalReader — subscribes to systemd-journald and yields entries."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from collections.abc import AsyncIterator
from threading import Thread
from typing import Any

from security_agent.monitors.filters import JournalFilter

logger = logging.getLogger("journald.reader")

try:
    from systemd import journal

    HAS_SYSTEMD = True
except ImportError:
    HAS_SYSTEMD = False
    journal = None


class JournalReaderState:
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"
    DEGRADED = "DEGRADED"


class JournalReader:
    """Reads journald entries asynchronously."""

    def __init__(
        self,
        filter_obj: JournalFilter | None = None,
        units: list[str] | None = None,
        identifiers: list[str] | None = None,
        priority: str = "info",
    ) -> None:
        self._filter = filter_obj
        self._units = units or []
        self._identifiers = identifiers or []
        self._priority = priority
        self._state = JournalReaderState.DISCONNECTED
        self._reconnect_count = 0
        self._entries_read = 0

    @property
    def state(self) -> str:
        return self._state

    @property
    def reconnect_count(self) -> int:
        return self._reconnect_count

    @property
    def entries_read(self) -> int:
        return self._entries_read

    async def read(self) -> AsyncIterator[dict[str, Any]]:
        if HAS_SYSTEMD:
            async for entry in self._read_native():
                yield entry
        else:
            async for entry in self._read_subprocess():
                yield entry

    async def close(self) -> None:
        self._state = JournalReaderState.DISCONNECTED

    async def _read_native(self) -> AsyncIterator[dict[str, Any]]:
        entry_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        def _reader_thread() -> None:
            try:
                j = journal.Reader()
                j.seek_tail()
                j.get_previous()
                if self._units:
                    for unit in self._units:
                        j.add_match(_SYSTEMD_UNIT=unit)
                if self._identifiers:
                    for ident in self._identifiers:
                        j.add_match(SYSLOG_IDENTIFIER=ident)
                prio_map = {
                    "emerg": 0,
                    "alert": 1,
                    "crit": 2,
                    "err": 3,
                    "warning": 4,
                    "notice": 5,
                    "info": 6,
                    "debug": 7,
                }
                j.log_level(prio_map.get(self._priority, 6))
                self._state = JournalReaderState.CONNECTED
                while True:
                    j.wait(-1)
                    for entry in j:
                        entry_queue.put_nowait(dict(entry))
                        self._entries_read += 1
            except Exception as e:
                logger.error("Journal reader thread error", extra={"error": str(e)})
                entry_queue.put_nowait(None)
            finally:
                try:
                    j.close()
                except Exception:
                    pass

        Thread(target=_reader_thread, daemon=True).start()

        while True:
            entry = await entry_queue.get()
            if entry is None:
                self._state = JournalReaderState.DISCONNECTED
                return
            yield entry

    async def _read_subprocess(self) -> AsyncIterator[dict[str, Any]]:
        cmd = ["journalctl", "--follow", "--output", "json", "--no-tail"]
        if self._units:
            for unit in self._units:
                cmd.extend(["--unit", unit])
        if self._identifiers:
            for ident in self._identifiers:
                cmd.extend(["--identifier", ident])
        prio_map = {
            "emerg": 0,
            "alert": 1,
            "crit": 2,
            "err": 3,
            "warning": 4,
            "notice": 5,
            "info": 6,
            "debug": 7,
        }
        cmd.extend(["--priority", str(prio_map.get(self._priority, 6))])

        while True:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env={**os.environ, "SYSTEMD_COLORS": "0"},
                )
                self._state = JournalReaderState.CONNECTED
                if proc.stdout is None:
                    raise RuntimeError("journalctl stdout is None")
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        continue
                    try:
                        yield json.loads(line_str)
                        self._entries_read += 1
                    except json.JSONDecodeError:
                        logger.warning(
                            "Malformed journal entry", extra={"line": line_str[:200]}
                        )
                await proc.wait()
                self._reconnect_count += 1
                self._state = JournalReaderState.RECONNECTING
                logger.warning(
                    "Journalctl process exited, reconnecting",
                    extra={"rc": proc.returncode, "reconnects": self._reconnect_count},
                )
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._reconnect_count += 1
                self._state = JournalReaderState.RECONNECTING
                logger.error(
                    "Journalctl error, reconnecting",
                    extra={"error": str(e), "reconnects": self._reconnect_count},
                )
                await asyncio.sleep(2.0)
