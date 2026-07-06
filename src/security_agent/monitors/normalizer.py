"""
JournalNormalizer — converts raw journal records into NormalizedJournalEvent.

This module contains zero detection logic.
Its only responsibility is field mapping and type normalization.
"""

from __future__ import annotations

import datetime
import socket
from typing import Any

from security_agent.monitors.models import NormalizedJournalEvent


class JournalNormalizer:
    """
    Converts raw journald record dicts into NormalizedJournalEvent instances.

    Handles:
    - Field name mapping (journald field names → normalized names)
    - Type conversion (string timestamps → datetime, etc.)
    - Missing field defaults
    - Malformed field recovery
    - Hostname resolution (cached)
    """

    def __init__(self) -> None:
        self._hostname: str = ""

    @property
    def hostname(self) -> str:
        if not self._hostname:
            self._hostname = socket.gethostname()
        return self._hostname

    def normalize(self, entry: dict[str, Any]) -> NormalizedJournalEvent:
        """Convert a raw journal entry into a normalized event.

        Args:
            entry: Raw journald record as dict with standard field names.

        Returns:
            NormalizedJournalEvent with all available fields populated.
        """
        return NormalizedJournalEvent(
            event_id=self._get_str(entry, "__CURSOR", ""),
            correlation_id="",
            timestamp=self._parse_timestamp(entry),
            hostname=self._get_hostname(entry),
            source_type="journald",
            source_name=self._get_source_name(entry),
            pid=self._get_int(entry, "_PID"),
            uid=self._get_int(entry, "_UID"),
            gid=self._get_int(entry, "_GID"),
            executable=self._get_str(entry, "_EXE"),
            command=self._get_str(entry, "_CMDLINE"),
            systemd_unit=self._get_str(entry, "_SYSTEMD_UNIT"),
            identifier=self._get_str(entry, "SYSLOG_IDENTIFIER"),
            facility=self._get_int(entry, "SYSLOG_FACILITY"),
            priority=self._get_int(entry, "PRIORITY"),
            transport=self._get_str(entry, "_TRANSPORT"),
            message=self._get_str(entry, "MESSAGE"),
            raw_fields=dict(entry),
        )

    def _get_hostname(self, entry: dict[str, Any]) -> str:
        """Extract hostname, falling back to local hostname."""
        return self._get_str(entry, "_HOSTNAME") or self.hostname

    def _get_source_name(self, entry: dict[str, Any]) -> str:
        """Derive a human-readable source name."""
        unit = self._get_str(entry, "_SYSTEMD_UNIT")
        if unit:
            return unit
        ident = self._get_str(entry, "SYSLOG_IDENTIFIER")
        if ident:
            return ident
        transport = self._get_str(entry, "_TRANSPORT")
        if transport:
            return f"journald.{transport}"
        return "journald"

    def _parse_timestamp(self, entry: dict[str, Any]) -> datetime.datetime:
        """Parse journal timestamp with fallback."""
        ts = entry.get("__REALTIME_TIMESTAMP")
        if ts is not None:
            try:
                # journald gives microseconds since epoch
                return datetime.datetime.fromtimestamp(
                    int(ts) / 1_000_000, tz=datetime.UTC
                )
            except (ValueError, TypeError, OSError):
                pass

        # Try monotonic timestamp
        ts = entry.get("__MONOTONIC_TIMESTAMP")
        if ts is not None:
            try:
                return datetime.datetime.fromtimestamp(
                    int(ts) / 1_000_000, tz=datetime.UTC
                )
            except (ValueError, TypeError, OSError):
                pass

        return datetime.datetime.now(tz=datetime.UTC)

    @staticmethod
    def _get_str(entry: dict[str, Any], key: str, default: str = "") -> str:
        """Safely extract a string field."""
        val = entry.get(key)
        if val is None:
            return default
        if isinstance(val, bytes):
            return val.decode("utf-8", errors="replace")
        return str(val)

    @staticmethod
    def _get_int(entry: dict[str, Any], key: str) -> int | None:
        """Safely extract an integer field."""
        val = entry.get(key)
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None
