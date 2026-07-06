"""
Normalized journal event model.

This is the universal intermediate representation for all raw log entries
regardless of source. Every monitor normalizes into this format.

Detectors and the pipeline consume NormalizedJournalEvent instances.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

PARSER_VERSION = "1.0"
NORMALIZATION_VERSION = "1.0"


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _new_uuid() -> str:
    return str(uuid.uuid4())


@dataclass(slots=True, frozen=True)
class NormalizedJournalEvent:
    """
    Universal normalized event for all log sources.

    Every monitor normalizes raw log entries into this structure.
    This is the contract that every future detector expects.

    Fields are grouped into:
      - core:       identity, timing, provenance
      - process:    originating process context
      - system:     systemd/syslog metadata
      - message:    log content and extra fields
      - metadata:   parser versioning
    """

    # === Core ===
    event_id: str = field(default_factory=_new_uuid)
    correlation_id: str = ""
    timestamp: datetime = field(default_factory=_now_utc)
    hostname: str = ""
    source_type: str = ""  # "journald", "logfile", "auditd", etc.
    source_name: str = ""  # "auth.log", "sshd.service", etc.

    # === Process ===
    pid: int | None = None
    uid: int | None = None
    gid: int | None = None
    executable: str | None = None
    command: str | None = None

    # === System ===
    systemd_unit: str | None = None
    identifier: str | None = None  # syslog identifier (e.g., "sshd", "sudo")
    facility: int | None = None
    priority: int | None = None
    transport: str | None = None  # "journal", "syslog", "stdout", "kernel"

    # === Message ===
    message: str = ""
    raw_fields: dict[str, Any] = field(default_factory=dict)

    # === Metadata ===
    parser_version: str = PARSER_VERSION
    normalization_version: str = NORMALIZATION_VERSION
