"""
SSH Detector Manager — orchestrates all SSH security detectors.

Coordinates parsing, detection, and result emission for the
SSH detector suite. Each sub-detector tracks its own state.
"""

from __future__ import annotations

import logging
from typing import Any

from security_agent.detectors.ssh.brute_force import BruteForceTracker
from security_agent.detectors.ssh.failed_login import FailedLoginTracker
from security_agent.detectors.ssh.impossible_travel import ImpossibleTravelTracker
from security_agent.detectors.ssh.invalid_user import InvalidUserTracker
from security_agent.detectors.ssh.parser import parse as parse_ssh
from security_agent.detectors.ssh.password_spray import PasswordSprayTracker
from security_agent.detectors.ssh.port_scan_hint import PortScanHintTracker
from security_agent.detectors.ssh.root_login import detect_root_login
from security_agent.detectors.ssh.session_abuse import SessionAbuseTracker
from security_agent.detectors.ssh.successful_login import SuccessfulLoginTracker

logger = logging.getLogger("detectors.ssh")


class SSHSecurityManager:
    """Orchestrates SSH security detection.

    Usage:
        mgr = SSHSecurityManager()
        results = mgr.analyze(raw_message)
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self._failed = FailedLoginTracker(
            max_failures=cfg.get("max_failures", 10),
            window=cfg.get("failure_window", 300),
        )
        self._success = SuccessfulLoginTracker()
        self._invalid = InvalidUserTracker(
            max_users=cfg.get("max_invalid_users", 5),
            window=cfg.get("invalid_window", 300),
        )
        self._spray = PasswordSprayTracker(
            max_total=cfg.get("spray_max_total", 30),
            max_per_user=cfg.get("spray_max_per_user", 3),
            window=cfg.get("spray_window", 600),
        )
        self._brute = BruteForceTracker(
            max_attempts=cfg.get("brute_max_attempts", 50),
            window=cfg.get("brute_window", 300),
        )
        self._travel = ImpossibleTravelTracker()
        self._session = SessionAbuseTracker(
            max_concurrent=cfg.get("max_concurrent", 5),
            reconnect_window=cfg.get("reconnect_window", 60),
        )
        self._scan_hint = PortScanHintTracker()

        # Whitelisted IPs
        self._trusted_ips: set[str] = set(cfg.get("trusted_ips", []))
        self._trusted_networks: list[str] = cfg.get("trusted_networks", [])

    def analyze(self, raw_message: str) -> list[dict[str, Any]]:
        """Analyze a raw SSH log line through all sub-detectors.

        Args:
            raw_message: Raw log line from journald.

        Returns:
            List of detection results (may be empty).
        """
        parsed = parse_ssh(raw_message)
        if not parsed.parsed:
            return []

        if self._is_trusted(parsed.source_ip):
            return []

        results: list[dict[str, Any]] = []

        # Failed login
        if parsed.event_type == "failed_password" and parsed.source_ip:
            r = self._failed.record(parsed.source_ip, parsed.username)
            if r["detected"]:
                results.append(r)

            # Root login check
            root_r = detect_root_login(parsed.username, parsed.event_type)
            if root_r["detected"]:
                results.append(root_r)

            # Invalid user tracking
            invalid_r = self._invalid.record(parsed.source_ip, parsed.username)
            if invalid_r["detected"]:
                results.append(invalid_r)

            # Password spray
            spray_r = self._spray.record(parsed.source_ip, parsed.username)
            if spray_r["detected"]:
                results.append(spray_r)

            # Brute force
            brute_r = self._brute.record(parsed.source_ip, parsed.username)
            if brute_r["detected"]:
                results.append(brute_r)

            # Scan hint
            self._scan_hint.record_ssh(parsed.source_ip)

        # Successful login
        elif parsed.event_type == "success":
            self._success.record(parsed.source_ip, parsed.username, parsed.auth_method)

            # If this IP had many failures before success, flag it
            failed_state = self._failed.record(parsed.source_ip, parsed.username)
            if failed_state["count"] > 0:
                results.append(
                    {
                        "detected": True,
                        "threat_type": "success_after_failures",
                        "source_ip": parsed.source_ip,
                        "username": parsed.username,
                        "previous_failures": failed_state["count"],
                        "confidence": min(50 + failed_state["count"] * 5, 95),
                        "severity": 9,
                    }
                )

            # Travel check
            travel_r = self._travel.record(parsed.source_ip, parsed.username)
            if travel_r["detected"]:
                results.append(travel_r)

        # Session tracking
        if parsed.event_type in ("failed_password", "success"):
            self._scan_hint.record_ssh(parsed.source_ip)

        return results

    def _is_trusted(self, ip: str) -> bool:
        if ip in self._trusted_ips:
            return True
        for network in self._trusted_networks:
            if ip.startswith(network.rstrip(".")):
                return True
        return False

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "tracked_failed_ips": self._failed.tracked_ips,
        }
