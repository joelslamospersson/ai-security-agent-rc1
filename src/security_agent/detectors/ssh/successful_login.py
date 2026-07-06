"""Successful login detector — tracks successful authentications."""

from __future__ import annotations

from typing import Any


class SuccessfulLoginTracker:
    """Tracks successful logins for session analysis."""

    def __init__(self) -> None:
        self._logins: dict[str, list[dict[str, Any]]] = {}

    def record(self, ip: str, username: str, auth_method: str) -> dict[str, Any]:
        entry = {"username": username, "auth_method": auth_method}
        if ip not in self._logins:
            self._logins[ip] = []
        self._logins[ip].append(entry)
        return {"detected": True, "threat_type": "successful_login", "confidence": 99}
