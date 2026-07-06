"""
SSH log parser — extracts structured data from SSH journal messages.

Handles OpenSSH log formats across distributions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParsedSSHEvent:
    """Structured data extracted from an SSH log line."""

    raw: str = ""
    event_type: str = ""  # failed_password, success, invalid_user, etc.
    username: str = ""
    source_ip: str = ""
    port: int = 0
    auth_method: str = ""  # password, publickey, keyboard-interactive, etc.
    pid: int = 0
    session_id: str = ""
    key_fingerprint: str = ""
    error_message: str = ""

    # Parsing metadata
    confidence: int = 0
    parsed: bool = False


# Regex patterns for SSH log messages
_FAILED_PASSWORD = re.compile(
    r"Failed password\s+(?:for\s+(?P<username>\S+)\s+)?"
    r"(?:invalid\s+user\s+(?P<invalid_user>\S+)\s+)?"
    r"from\s+(?P<ip>\d+\.\d+\.\d+\.\d+(?:%[^\s]+)?)\s+"
    r"port\s+(?P<port>\d+)"
    r"(?:\s+(?P<auth>\S+))?"
)

_SUCCESS = re.compile(
    r"Accepted\s+(?P<auth>\S+)\s+for\s+(?P<username>\S+)\s+"
    r"from\s+(?P<ip>\d+\.\d+\.\d+\.\d+(?:%[^\s]+)?)\s+"
    r"port\s+(?P<port>\d+)"
)

_INVALID_USER = re.compile(
    r"Invalid\s+user\s+(?P<username>\S+)\s+from\s+(?P<ip>\d+\.\d+\.\d+\.\d+)"
)

_DISCONNECT = re.compile(
    r"Connection\s+(?:closed|reset)\s+by\s+(?P<ip>\d+\.\d+\.\d+\.\d+)"
)

_AUTH_FAILURE = re.compile(
    r"authentication\s+failure.*?(?:for\s+(?P<username>\S+))?"
    r".*?(?:from\s+(?P<ip>\d+\.\d+\.\d+\.\d+))?"
)

_SESSION_OPEN = re.compile(
    r"session\s+opened\s+for\s+user\s+(?P<username>\S+)"
    r"(?:\s+by\s+(?P<uid>\S+))?"
)

_SESSION_CLOSE = re.compile(r"session\s+closed\s+for\s+user\s+(?P<username>\S+)")


def parse(message: str) -> ParsedSSHEvent:
    """Parse an SSH log message and return structured data."""
    result = ParsedSSHEvent(raw=message)

    # Failed password
    m = _FAILED_PASSWORD.search(message)
    if m:
        username = m.group("username") or m.group("invalid_user") or ""
        result.event_type = "failed_password"
        result.username = username
        result.source_ip = m.group("ip") or ""
        result.port = int(m.group("port") or 0)
        result.auth_method = m.group("auth") or "password"
        result.confidence = 95
        result.parsed = True
        return result

    # Successful authentication
    m = _SUCCESS.search(message)
    if m:
        result.event_type = "success"
        result.username = m.group("username") or ""
        result.source_ip = m.group("ip") or ""
        result.port = int(m.group("port") or 0)
        result.auth_method = m.group("auth") or ""
        result.confidence = 99
        result.parsed = True
        return result

    # Invalid user
    m = _INVALID_USER.search(message)
    if m:
        result.event_type = "invalid_user"
        result.username = m.group("username") or ""
        result.source_ip = m.group("ip") or ""
        result.confidence = 95
        result.parsed = True
        return result

    # Disconnect
    m = _DISCONNECT.search(message)
    if m:
        result.event_type = "disconnect"
        result.source_ip = m.group("ip") or ""
        result.parsed = True
        return result

    # Authentication failure (PAM)
    m = _AUTH_FAILURE.search(message)
    if m:
        result.event_type = "auth_failure"
        result.username = m.group("username") or ""
        result.source_ip = m.group("ip") or ""
        result.confidence = 80
        result.parsed = True
        return result

    # Session open
    m = _SESSION_OPEN.search(message)
    if m:
        result.event_type = "session_open"
        result.username = m.group("username") or ""
        result.parsed = True
        return result

    # Session close
    m = _SESSION_CLOSE.search(message)
    if m:
        result.event_type = "session_close"
        result.username = m.group("username") or ""
        result.parsed = True
        return result

    return result


def extract_username(message: str) -> str:
    """Quick username extraction without full parsing."""
    m = re.search(r"(?:for|user)\s+(\S+)", message)
    return m.group(1) if m else ""


def extract_ip(message: str) -> str:
    """Quick IP extraction without full parsing."""
    m = re.search(r"from\s+(\d+\.\d+\.\d+\.\d+)", message)
    return m.group(1) if m else ""
