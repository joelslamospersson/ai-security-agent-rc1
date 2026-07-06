"""Failed login detector — tracks failed SSH authentication attempts."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


class FailedLoginTracker:
    """Tracks failed SSH login attempts per IP with configurable thresholds."""

    def __init__(self, max_failures: int = 5, window: int = 300) -> None:
        self._max_failures = max_failures
        self._window = window
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def record(self, ip: str, username: str) -> dict[str, Any]:
        now = time.time()
        self._attempts[ip].append(now)
        recent = [t for t in self._attempts[ip] if now - t < self._window]
        self._attempts[ip] = recent
        count = len(recent)

        if count >= self._max_failures:
            return {
                "detected": True,
                "count": count,
                "window": self._window,
                "threshold": self._max_failures,
                "threat_type": "excessive_failed_logins",
                "confidence": min(50 + count * 5, 95),
            }

        return {"detected": False, "count": count}

    def reset(self, ip: str) -> None:
        self._attempts.pop(ip, None)

    @property
    def tracked_ips(self) -> int:
        return len(self._attempts)
