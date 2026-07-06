"""Impossible travel detector — flags geographically impossible logins (interface)."""

from __future__ import annotations

from typing import Any


class ImpossibleTravelTracker:
    """Detects login pairs from geographically impossible locations.

    Interface only — requires GeoIP/ASN enrichment to be connected.
    Currently records login locations and flags rapid geographic changes.
    """

    def __init__(self, min_speed_kmh: int = 900) -> None:
        self._min_speed_kmh = min_speed_kmh
        self._last_login: dict[str, dict[str, Any]] = {}

    def record(self, ip: str, username: str) -> dict[str, Any]:
        prev = self._last_login.get(username)
        self._last_login[username] = {"ip": ip}

        if prev and prev.get("ip") and prev["ip"] != ip:
            return {
                "detected": True,
                "threat_type": "impossible_travel",
                "previous_ip": prev["ip"],
                "current_ip": ip,
                "confidence": 50,
                "severity": 5,
                "note": "GeoIP data required for full verification",
            }

        return {"detected": False}
