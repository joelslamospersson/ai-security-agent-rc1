"""Brute force detector — detects high-rate authentication attempts."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


class BruteForceTracker:
    """Detects brute force attacks: many attempts on few usernames.

    High rate + low username diversity = brute force.
    """

    def __init__(self, max_attempts: int = 50, window: int = 300) -> None:
        self._max_attempts = max_attempts
        self._window = window
        self._attempts: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def record(self, ip: str, username: str) -> dict[str, Any]:
        now = time.time()
        self._attempts[ip].append({"username": username, "time": now})
        recent = [a for a in self._attempts[ip] if now - a["time"] < self._window]
        self._attempts[ip] = recent

        count = len(recent)
        distinct_users = len({a["username"] for a in recent})
        rate = count / (self._window / 60)  # attempts per minute

        if count >= self._max_attempts and distinct_users <= 5:
            return {
                "detected": True,
                "count": count,
                "distinct_users": distinct_users,
                "rate_per_minute": round(rate, 1),
                "window": self._window,
                "threshold": self._max_attempts,
                "threat_type": "ssh_brute_force",
                "confidence": min(70 + min(distinct_users, 5) * 3, 95),
                "severity": 8,
            }

        return {"detected": False, "count": count, "rate": round(rate, 1)}
