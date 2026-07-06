"""Session abuse detector — tracks anomalous SSH session behavior."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


class SessionAbuseTracker:
    """Tracks SSH session patterns for abuse indicators.

    Monitors:
    - Multiple simultaneous sessions from same IP
    - Rapid reconnect loops
    - Suspicious session durations
    """

    def __init__(self, max_concurrent: int = 5, reconnect_window: int = 60) -> None:
        self._max_concurrent = max_concurrent
        self._reconnect_window = reconnect_window
        self._sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._reconnects: dict[str, list[float]] = defaultdict(list)

    def record_open(
        self, ip: str, username: str, session_id: str = ""
    ) -> dict[str, Any]:
        now = time.time()
        self._sessions[ip].append(
            {
                "username": username,
                "session_id": session_id,
                "open_time": now,
                "closed": False,
            }
        )

        active = [s for s in self._sessions[ip] if not s["closed"]]
        if len(active) >= self._max_concurrent:
            return {
                "detected": True,
                "threat_type": "concurrent_sessions",
                "active_sessions": len(active),
                "threshold": self._max_concurrent,
                "confidence": 70,
                "severity": 5,
            }

        return {"detected": False, "active_sessions": len(active)}

    def record_close(self, ip: str, username: str) -> dict[str, Any]:
        now = time.time()
        for s in reversed(self._sessions[ip]):
            if not s["closed"]:
                s["closed"] = True
                s["close_time"] = now
                duration = now - s["open_time"]
                break
        else:
            return {"detected": False}

        self._reconnects[ip].append(now)
        recent = [t for t in self._reconnects[ip] if now - t < self._reconnect_window]

        if len(recent) >= 5:
            return {
                "detected": True,
                "threat_type": "rapid_reconnect",
                "reconnects": len(recent),
                "window": self._reconnect_window,
                "confidence": 65,
                "severity": 5,
            }

        return {"detected": False}
