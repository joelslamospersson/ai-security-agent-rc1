"""
Log formatter — human-readable and JSONL log formatting.

Supports sensitive information masking (IPs, tokens, secrets).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import structlog

from management_server.logging.models import LogCategory, LogEntry

logger = structlog.get_logger("logging.formatter")

SENSITIVE_PATTERNS: list[tuple[str, str]] = [
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "IP"),  # IPs
    (r"[A-Za-z0-9+/=]{40,}", "TOKEN"),  # Base64 tokens
    (r"(?i)(token|secret|password|key|private_key)[=:]\s*\S+", "SECRET"),
    (r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", "EMAIL"),  # Emails
    (r"\b[0-9a-f]{64}\b", "HASH"),  # SHA-256 hashes
    (r"\b[0-9a-f]{32}\b", "FP"),  # MD5/Fingerprints
]

MASK_REPLACEMENTS: dict[str, str] = {
    "IP": "x.x.x.x",
    "TOKEN": "[REDACTED]",
    "SECRET": "[REDACTED]",
    "EMAIL": "[REDACTED]",
    "HASH": "[REDACTED]",
    "FP": "[REDACTED]",
}


class LogFormatter:
    """Formats log entries for human-readable and JSONL output."""

    SEPARATOR = "─" * 60

    @classmethod
    def format_human(cls, entry: LogEntry) -> str:
        """Format a log entry for human reading."""
        lines = [
            cls.SEPARATOR,
            "",
            "Timestamp:",
            f"  {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "Severity:",
            f"  {entry.severity}",
            "",
        ]
        if entry.machine_id:
            lines.extend(["Machine:", f"  {cls.mask_value(entry.machine_id)}", ""])
        if entry.correlation_id:
            lines.extend(["Correlation ID:", f"  {cls.mask_value(entry.correlation_id)}", ""])
        if entry.event_type:
            lines.extend(["Event:", f"  {entry.event_type}", ""])
        if entry.description:
            lines.extend(["Description:", f"  {cls.mask_value(entry.description)}", ""])
        if entry.source:
            lines.extend(["Source:", f"  {cls.mask_value(entry.source)}", ""])
        if entry.threat_score:
            lines.extend(["Threat Score:", f"  {entry.threat_score:.0f}", ""])
        if entry.confidence:
            lines.extend(["Confidence:", f"  {entry.confidence:.0f}%", ""])
        if entry.policy:
            lines.extend(["Policy:", f"  {entry.policy}", ""])
        if entry.action:
            lines.extend(["Action:", f"  {entry.action}", ""])
        if entry.metadata:
            meta_str = json.dumps(cls.mask_dict(entry.metadata), indent=2)
            lines.extend(["Metadata:", f"  {meta_str}", ""])

        lines.append(cls.SEPARATOR)
        return "\n".join(lines)

    @classmethod
    def format_jsonl(cls, entry: LogEntry) -> str:
        """Format a log entry as a single JSON line."""
        data = {
            "timestamp": entry.timestamp.isoformat(),
            "severity": entry.severity,
            "category": entry.category.value,
            "machine_id": cls.mask_value(entry.machine_id),
            "correlation_id": cls.mask_value(entry.correlation_id),
            "event_type": entry.event_type,
            "description": cls.mask_value(entry.description),
            "source": cls.mask_value(entry.source),
            "threat_score": entry.threat_score,
            "confidence": entry.confidence,
            "policy": entry.policy,
            "action": entry.action,
            "metadata": cls.mask_dict(entry.metadata),
        }
        return json.dumps(data, default=str, separators=(",", ":"))

    @staticmethod
    def mask_value(value: str) -> str:
        """Mask sensitive information in a string value."""
        if not value:
            return value
        result = value
        for pattern, label in SENSITIVE_PATTERNS:
            if label in ("IP", "HASH", "FP"):
                result = re.sub(pattern, MASK_REPLACEMENTS.get(label, "[REDACTED]"), result)
            else:
                result = re.sub(
                    pattern, MASK_REPLACEMENTS.get(label, "[REDACTED]"), result, flags=re.IGNORECASE
                )
        return result

    @staticmethod
    def mask_dict(data: dict[str, Any]) -> dict[str, Any]:
        """Recursively mask sensitive values in a dict."""
        result: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = LogFormatter.mask_value(value)
            elif isinstance(value, dict):
                result[key] = LogFormatter.mask_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    LogFormatter.mask_value(v) if isinstance(v, str) else v for v in value
                ]
            else:
                result[key] = value
        return result

    @staticmethod
    def get_log_filename(category: LogCategory, date: str | None = None) -> str:
        """Get the log file name for a category."""
        if date is None:
            date = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        return f"{category.value}-{date}.log"
