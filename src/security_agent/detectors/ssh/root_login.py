"""Root login detector — flags direct root SSH attempts (usually disabled)."""

from __future__ import annotations

from typing import Any


def detect_root_login(username: str, event_type: str) -> dict[str, Any]:
    """Detect direct root login attempts via SSH.

    Root login via SSH is typically disabled and almost always
    indicates malicious scanning or brute-force targeting.
    """
    if username == "root":
        return {
            "detected": True,
            "threat_type": "root_login_attempt",
            "confidence": 70 if event_type == "failed_password" else 85,
            "severity": 6,
        }
    return {"detected": False}
