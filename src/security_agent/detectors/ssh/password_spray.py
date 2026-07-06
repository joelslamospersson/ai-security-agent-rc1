"""Password spraying detector — detects low-and-slow attacks across many usernames."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


class PasswordSprayTracker:
    """Detects password spraying: few attempts per user, many users from one IP.

    Unlike brute force (many attempts on few users), password spraying
    tries one password against many usernames, evading per-account lockouts.
    """

    def __init__(
        self, max_total: int = 30, max_per_user: int = 3, window: int = 600
    ) -> None:
        self._max_total = max_total
        self._max_per_user = max_per_user
        self._window = window
        self._attempts: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def record(self, ip: str, username: str) -> dict[str, Any]:
        now = time.time()
        self._attempts[ip][username].append(now)

        total = 0
        for user, times in list(self._attempts[ip].items()):
            self._attempts[ip][user] = [t for t in times if now - t < self._window]
            total += len(self._attempts[ip][user])

        distinct_users = sum(1 for u in self._attempts[ip] if self._attempts[ip][u])

        # Password spray indicators: many users, few attempts per user
        if (
            total >= self._max_total
            and distinct_users >= 5
            and max(len(v) for v in self._attempts[ip].values()) <= self._max_per_user
        ):
            return {
                "detected": True,
                "total_attempts": total,
                "distinct_users": distinct_users,
                "max_per_user": max(len(v) for v in self._attempts[ip].values()),
                "threat_type": "password_spraying",
                "confidence": min(60 + distinct_users * 2, 90),
                "severity": 7,
            }

        return {
            "detected": False,
            "total_attempts": total,
            "distinct_users": distinct_users,
        }
