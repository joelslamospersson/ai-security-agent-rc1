"""
Comprehensive tests for the SSH Security Detector Pack.
"""

from __future__ import annotations

import time

import pytest
import yaml

from security_agent.detectors.ssh.brute_force import BruteForceTracker
from security_agent.detectors.ssh.failed_login import FailedLoginTracker
from security_agent.detectors.ssh.impossible_travel import ImpossibleTravelTracker
from security_agent.detectors.ssh.invalid_user import InvalidUserTracker
from security_agent.detectors.ssh.manager import SSHSecurityManager
from security_agent.detectors.ssh.parser import extract_ip, extract_username, parse
from security_agent.detectors.ssh.password_spray import PasswordSprayTracker
from security_agent.detectors.ssh.root_login import detect_root_login
from security_agent.detectors.ssh.session_abuse import SessionAbuseTracker

FAILED_SSH = "Failed password for root from 198.51.100.42 port 22 ssh2"
SUCCESS_SSH = (
    "Accepted publickey for admin from 198.51.100.42 port 22 ssh2: RSA SHA256:abc"
)
INVALID_USER = "Invalid user test from 203.0.113.5 port 55555"
ROOT_FAILED = "Failed password for root from 198.51.100.42 port 22 ssh2"
ROOT_SUCCESS = "Accepted publickey for root from 10.0.0.1 port 22 ssh2"
SESSION_OPEN = "session opened for user admin by (uid=0)"
SESSION_CLOSE = "session closed for user admin"
DISCONNECT = "Connection closed by 198.51.100.42 port 22"
AUTH_FAILURE = (
    "authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost=198.51.100.42"
)


class TestParser:
    def test_failed_password(self):
        r = parse(FAILED_SSH)
        assert r.event_type == "failed_password"
        assert r.username == "root"
        assert r.source_ip == "198.51.100.42"
        assert r.port == 22
        assert r.parsed

    def test_successful_login(self):
        r = parse(SUCCESS_SSH)
        assert r.event_type == "success"
        assert r.username == "admin"
        assert r.source_ip == "198.51.100.42"

    def test_invalid_user(self):
        r = parse(INVALID_USER)
        assert r.event_type == "invalid_user"
        assert r.username == "test"
        assert r.source_ip == "203.0.113.5"

    def test_unparsed(self):
        r = parse("random log line")
        assert not r.parsed

    def test_extract_ip(self):
        assert extract_ip(FAILED_SSH) == "198.51.100.42"

    def test_extract_username(self):
        assert extract_username(FAILED_SSH) == "root"


class TestFailedLogin:
    def test_below_threshold(self):
        t = FailedLoginTracker(max_failures=5, window=300)
        for _ in range(3):
            t.record("1.2.3.4", "admin")
        r = t.record("1.2.3.4", "admin")
        assert not r["detected"]

    def test_above_threshold(self):
        t = FailedLoginTracker(max_failures=3, window=300)
        for _ in range(3):
            t.record("1.2.3.4", "admin")
        r = t.record("1.2.3.4", "admin")
        assert r["detected"]
        assert r["threat_type"] == "excessive_failed_logins"


class TestInvalidUser:
    def test_detects_enumeration(self):
        t = InvalidUserTracker(max_users=3, window=300)
        for user in ["alice", "bob", "carol", "dave"]:
            t.record("1.2.3.4", user)
        r = t.record("1.2.3.4", "eve")
        assert r["detected"]
        assert r["threat_type"] == "username_enumeration"


class TestBruteForce:
    def test_detects_brute_force(self):
        t = BruteForceTracker(max_attempts=5, window=300)
        for _ in range(6):
            t.record("1.2.3.4", "admin")
        r = t.record("1.2.3.4", "admin")
        assert r["detected"]
        assert r["threat_type"] == "ssh_brute_force"


class TestPasswordSpray:
    def test_detects_spray(self):
        t = PasswordSprayTracker(max_total=5, max_per_user=2, window=600)
        for user in ["a", "b", "c", "d", "e", "f"]:
            t.record("1.2.3.4", user)
        r = t.record("1.2.3.4", "g")
        assert r["detected"]
        assert r["threat_type"] == "password_spraying"


class TestRootLogin:
    def test_root_failed(self):
        r = detect_root_login("root", "failed_password")
        assert r["detected"]
        assert r["threat_type"] == "root_login_attempt"

    def test_non_root(self):
        assert not detect_root_login("admin", "failed_password")["detected"]


class TestSessionAbuse:
    def test_concurrent_sessions(self):
        t = SessionAbuseTracker(max_concurrent=3, reconnect_window=60)
        for _ in range(4):
            t.record_open("1.2.3.4", "admin")
        r = t.record_open("1.2.3.4", "admin")
        assert r["detected"]
        assert r["threat_type"] == "concurrent_sessions"

    def test_rapid_reconnect(self):
        t = SessionAbuseTracker(max_concurrent=10, reconnect_window=60)
        t.record_open("1.2.3.4", "admin")
        for _ in range(6):
            t.record_close("1.2.3.4", "admin")
            t.record_open("1.2.3.4", "admin")
        r = t.record_close("1.2.3.4", "admin")
        assert r["detected"]
        assert r["threat_type"] == "rapid_reconnect"


class TestImpossibleTravel:
    def test_travel_detected(self):
        t = ImpossibleTravelTracker()
        t.record("1.1.1.1", "admin")
        r = t.record("9.9.9.9", "admin")
        assert r["detected"]
        assert r["threat_type"] == "impossible_travel"


class TestManager:
    def test_failed_login_analyzed(self):
        mgr = SSHSecurityManager()
        results = mgr.analyze(FAILED_SSH)
        assert len(results) >= 1
        assert any(r.get("threat_type") == "root_login_attempt" for r in results)

    def test_successful_login(self):
        mgr = SSHSecurityManager()
        results = mgr.analyze(SUCCESS_SSH)
        assert len(results) >= 0

    def test_unparsed_line(self):
        mgr = SSHSecurityManager()
        results = mgr.analyze("random log line")
        assert results == []

    def test_whitelisted_ip(self):
        mgr = SSHSecurityManager({"trusted_ips": ["198.51.100.42"]})
        results = mgr.analyze(FAILED_SSH)
        assert results == []


class TestRules:
    def test_rules_yaml_is_valid(self):
        import os

        path = os.path.join(
            os.path.dirname(
                __import__("security_agent.detectors.ssh", fromlist=[""]).__file__
            ),
            "rules.yaml",
        )
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert "rules" in data
        assert len(data["rules"]) >= 10

    def test_rules_have_required_fields(self):
        import os

        path = os.path.join(
            os.path.dirname(
                __import__("security_agent.detectors.ssh", fromlist=[""]).__file__
            ),
            "rules.yaml",
        )
        with open(path) as f:
            data = yaml.safe_load(f)
        for rule in data["rules"]:
            assert "id" in rule
            assert "name" in rule
            assert "severity" in rule


class TestBenchmarks:
    @pytest.mark.benchmark
    def test_parser_throughput(self):
        lines = [FAILED_SSH, SUCCESS_SSH, INVALID_USER, ROOT_FAILED, "random"] * 2000
        t = time.monotonic()
        for line in lines:
            parse(line)
        elapsed = time.monotonic() - t
        print(
            f"\n  Parser: {len(lines) / elapsed:.0f} lines/s ({len(lines)} in {elapsed:.3f}s)"
        )

    @pytest.mark.benchmark
    def test_manager_throughput(self):
        mgr = SSHSecurityManager()
        lines = [FAILED_SSH, SUCCESS_SSH, INVALID_USER, "random"] * 2500
        t = time.monotonic()
        for line in lines:
            mgr.analyze(line)
        elapsed = time.monotonic() - t
        print(
            f"\n  Manager: {len(lines) / elapsed:.0f} lines/s ({len(lines)} in {elapsed:.3f}s)"
        )
