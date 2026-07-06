"""
Ban history — in-memory store tracking all ban decisions.

Designed so the backend can be swapped for SQLite later.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class BanRecord:
    """Mutable ban record for a single entity."""

    entity: str = ""
    entity_type: str = ""
    first_ban: float = 0.0
    last_ban: float = 0.0
    total_bans: int = 0
    is_permanently_banned: bool = False
    active_level: int = 0
    ban_expires: float = 0.0


class BanHistory:
    """In-memory ban history storage.

    O(1) lookup by (entity_type, entity).
    API designed for future SQLite backend swap.
    """

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], BanRecord] = {}

    def record_ban(
        self,
        entity: str,
        entity_type: str,
        level: int,
        duration: int,
    ) -> BanRecord:
        """Record a ban decision."""
        now = time.time()
        key = (entity_type, entity)

        if key in self._records:
            rec = self._records[key]
            rec.last_ban = now
            rec.total_bans += 1
            rec.active_level = level
            if duration > 0:
                rec.ban_expires = now + duration
            else:
                rec.ban_expires = 0  # permanent or warning
            if level >= 7:
                rec.is_permanently_banned = True
        else:
            rec = BanRecord(
                entity=entity,
                entity_type=entity_type,
                first_ban=now,
                last_ban=now,
                total_bans=1,
                active_level=level,
                ban_expires=now + duration if duration > 0 else 0,
                is_permanently_banned=(level >= 7),
            )
            self._records[key] = rec

        return rec

    def lookup(self, entity: str, entity_type: str) -> BanRecord | None:
        return self._records.get((entity_type, entity))

    def count(self) -> int:
        return len(self._records)

    def list_active(self) -> list[BanRecord]:
        now = time.time()
        return [
            r
            for r in self._records.values()
            if r.ban_expires == 0 or r.ban_expires > now
        ]

    def clear(self) -> None:
        self._records.clear()
