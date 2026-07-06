"""Invalid user detector — tracks attempts with non-existent usernames."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


class InvalidUserTracker:
    """Tracks invalid SSH username attempts (botnet behavior)."""

    def __init__(self, max_users: int = 5, window: int = 300) -> None:
        self._max_users = max_users
        self._window = window
        self._attempts: dict[str, dict[str, float]] = defaultdict(dict)

    def record(self, ip: str, username: str) -> dict[str, Any]:
        now = time.time()
        self._attempts[ip][username] = now
        recent = {u: t for u, t in self._attempts[ip].items() if now - t < self._window}
        self._attempts[ip] = recent

        if len(recent) >= self._max_users:
            return {
                "detected": True,
                "distinct_users": len(recent),
                "window": self._window,
                "threshold": self._max_users,
                "threat_type": "username_enumeration",
                "confidence": min(70 + len(recent) * 3, 95),
            }

        return {"detected": False, "distinct_users": len(recent)}
