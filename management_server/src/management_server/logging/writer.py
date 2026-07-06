"""
Log writer — writes formatted logs to the filesystem.

Manages directory structure and file handles.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog

from management_server.logging.exceptions import LogWriteError
from management_server.logging.formatter import LogFormatter
from management_server.logging.models import (
    DEFAULT_LOG_ROOT,
    FALLBACK_LOG_ROOT,
    LOG_DIRECTORIES,
    LogEntry,
)

logger = structlog.get_logger("logging.writer")

LOG_ROOT_ENV_VAR = "AISEC_LOG_ROOT"


class LogWriter:
    """Writes log entries to the filesystem.

    Creates directories automatically, writes both human and JSONL logs.
    """

    def __init__(self, log_root: str | None = None) -> None:
        self._log_root = self._resolve_root(log_root)
        self._ensure_directories()
        self._human_writers: dict[str, Any] = {}
        self._jsonl_writers: dict[str, Any] = {}

    def _resolve_root(self, override: str | None) -> Path:
        if override:
            override_path: Path = Path(override)
            return override_path
        env_root = os.environ.get(LOG_ROOT_ENV_VAR)
        if env_root:
            env_path: Path = Path(env_root)
            return env_path
        default = DEFAULT_LOG_ROOT
        try:
            default.mkdir(parents=True, exist_ok=True)
            test_file = default / ".write_test"
            test_file.touch()
            test_file.unlink()
            root_result: Path = default
            return root_result
        except (OSError, PermissionError):
            fallback = FALLBACK_LOG_ROOT
            fallback.mkdir(parents=True, exist_ok=True)
            logger.warning("Using fallback log directory", path=str(fallback))
            fb_path: Path = fallback
            return fb_path

    def _ensure_directories(self) -> None:
        """Create all required log directories."""
        for cat_dir in LOG_DIRECTORIES.values():
            (self._log_root / cat_dir).mkdir(parents=True, exist_ok=True)
        (self._log_root / "json").mkdir(parents=True, exist_ok=True)
        (self._log_root / "reports" / "incidents").mkdir(parents=True, exist_ok=True)
        (self._log_root / "reports" / "daily").mkdir(parents=True, exist_ok=True)
        (self._log_root / "reports" / "weekly").mkdir(parents=True, exist_ok=True)
        (self._log_root / "reports" / "monthly").mkdir(parents=True, exist_ok=True)

    async def write(self, entry: LogEntry) -> dict[str, Any]:
        """Write a log entry to both human and JSONL files."""
        try:
            cat_dir = LOG_DIRECTORIES.get(entry.category, "management")
            date = entry.timestamp.strftime("%Y-%m-%d")

            # Human-readable log
            human_path = self._log_root / cat_dir / f"{entry.category.value}-{date}.log"
            human_content = LogFormatter.format_human(entry) + "\n"
            with open(human_path, "a") as f:
                f.write(human_content)

            # JSONL log
            jsonl_path = self._log_root / "json" / f"{entry.category.value}-{date}.jsonl"
            jsonl_content = LogFormatter.format_jsonl(entry) + "\n"
            with open(jsonl_path, "a") as f:
                f.write(jsonl_content)

            return {
                "human_path": str(human_path),
                "jsonl_path": str(jsonl_path),
                "bytes_written": len(human_content.encode()) + len(jsonl_content.encode()),
            }
        except OSError as e:
            raise LogWriteError(str(entry.category), str(e)) from e

    async def write_raw(
        self, path: str, content: str, category: str = "management"
    ) -> dict[str, Any]:
        """Write raw content to a specific log path."""
        try:
            file_path = self._log_root / category / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)
            return {"path": str(file_path), "bytes_written": len(content.encode())}
        except OSError as e:
            raise LogWriteError(path, str(e)) from e

    async def write_report(self, report_path: str, content: str) -> dict[str, Any]:
        """Write a report file."""
        return await self.write_raw(report_path, content, "reports")

    @property
    def log_root(self) -> Path:
        return self._log_root
