"""
Configuration-driven filtering for journal entries.

Filters are applied before normalization to avoid unnecessary work.
All filter criteria are optional and AND-combined.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JournalFilter:
    """
    Filter criteria for journal entries.

    All specified criteria must match (AND logic).
    Empty/unset criteria always match.

    Examples:
        # Only SSH-related messages
        JournalFilter(systemd_units=["ssh.service", "sshd.service"])

        # Only error priority and above
        JournalFilter(priority_max=3)

        # Only sudo and auth identifiers
        JournalFilter(identifiers=["sudo", "sshd", "auth"])
    """

    systemd_units: list[str] = field(default_factory=list)
    identifiers: list[str] = field(default_factory=list)
    transports: list[str] = field(default_factory=list)
    priority_max: int | None = None
    priority_min: int | None = None
    message_patterns: list[str] = field(default_factory=list)
    exclude_units: list[str] = field(default_factory=list)
    exclude_identifiers: list[str] = field(default_factory=list)

    def matches(self, entry: dict[str, Any]) -> bool:
        """Check if a journal entry matches this filter."""
        # Check included units
        if self.systemd_units:
            unit = entry.get("_SYSTEMD_UNIT", "") or ""
            if not any(unit == u or unit.endswith(f"/{u}") for u in self.systemd_units):
                return False

        # Check excluded units
        if self.exclude_units:
            unit = entry.get("_SYSTEMD_UNIT", "") or ""
            if any(unit == u or unit.endswith(f"/{u}") for u in self.exclude_units):
                return False

        # Check identifiers
        if self.identifiers:
            ident = entry.get("SYSLOG_IDENTIFIER", "") or ""
            if ident not in self.identifiers:
                return False

        # Check excluded identifiers
        if self.exclude_identifiers:
            ident = entry.get("SYSLOG_IDENTIFIER", "") or ""
            if ident in self.exclude_identifiers:
                return False

        # Check transports
        if self.transports:
            transport = entry.get("_TRANSPORT", "") or ""
            if transport not in self.transports:
                return False

        # Check priority range
        prio = entry.get("PRIORITY")
        if prio is not None:
            try:
                prio_int = int(prio)
                if self.priority_max is not None and prio_int > self.priority_max:
                    return False
                if self.priority_min is not None and prio_int < self.priority_min:
                    return False
            except (ValueError, TypeError):
                pass

        # Check message patterns
        if self.message_patterns:
            msg = entry.get("MESSAGE", "") or ""
            if not any(re.search(p, msg, re.IGNORECASE) for p in self.message_patterns):
                return False

        return True

    @staticmethod
    def from_config(config: dict[str, Any]) -> JournalFilter:
        """Create a JournalFilter from a configuration dict."""
        return JournalFilter(
            systemd_units=config.get("systemd_units", []),
            identifiers=config.get("identifiers", []),
            transports=config.get("transports", []),
            priority_max=config.get("priority_max"),
            priority_min=config.get("priority_min"),
            message_patterns=config.get("message_patterns", []),
            exclude_units=config.get("exclude_units", []),
            exclude_identifiers=config.get("exclude_identifiers", []),
        )
