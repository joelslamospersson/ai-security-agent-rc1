"""
Log retention — removes expired log files based on configurable retention policy.

Default: 30 days.
Never removes today's logs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger("logging.retention")

SUPPORTED_RETENTION_DAYS = {7, 30, 90, 365}
DEFAULT_RETENTION_DAYS = 30
MAX_LOG_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_REPORT_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_TOTAL_STORAGE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB


class RetentionManager:
    """Manages log retention and disk usage protection."""

    def __init__(
        self,
        log_root: Path,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        max_total_bytes: int = MAX_TOTAL_STORAGE_BYTES,
    ) -> None:
        self._log_root = log_root
        self._retention_days = max(1, min(retention_days, max(SUPPORTED_RETENTION_DAYS)))
        self._max_total_bytes = max_total_bytes

    async def enforce(self) -> dict[str, Any]:
        """Enforce retention policy across all log directories.

        Returns summary of cleanup actions.
        """
        now = datetime.now(tz=UTC)
        cutoff = now - timedelta(days=self._retention_days)
        today = now.strftime("%Y-%m-%d")

        deleted_files = 0
        deleted_bytes = 0
        total_bytes = 0

        # Remove expired files
        for path in self._log_root.rglob("*"):
            if not path.is_file():
                continue
            # Never remove today's files
            if today in path.name:
                total_bytes += path.stat().st_size
                continue

            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if mtime < cutoff:
                try:
                    deleted_bytes += path.stat().st_size
                    path.unlink()
                    deleted_files += 1
                except OSError as e:
                    logger.warning("Failed to delete expired log", path=str(path), error=str(e))
            else:
                total_bytes += path.stat().st_size

        # Disk usage protection: if over limit, remove oldest compressed files
        if total_bytes > self._max_total_bytes:
            excess = total_bytes - self._max_total_bytes
            removed = await self._remove_oldest(deleted_bytes + excess)
            deleted_files += removed["files"]
            deleted_bytes += removed["bytes"]

        logger.info(
            "Retention enforced",
            retention_days=self._retention_days,
            deleted_files=deleted_files,
            deleted_mb=round(deleted_bytes / 1024 / 1024, 2),
            total_mb=round(total_bytes / 1024 / 1024, 2),
        )

        return {
            "retention_days": self._retention_days,
            "deleted_files": deleted_files,
            "deleted_bytes": deleted_bytes,
            "total_bytes": total_bytes,
        }

    async def _remove_oldest(self, target_bytes: int) -> dict[str, int]:
        """Remove oldest compressed files until target bytes freed."""
        files: list[Path] = []
        for path in self._log_root.rglob("*.gz"):
            files.append(path)

        files.sort(key=lambda p: p.stat().st_mtime)

        removed_files = 0
        removed_bytes = 0
        for path in files:
            if removed_bytes >= target_bytes:
                break
            try:
                removed_bytes += path.stat().st_size
                path.unlink()
                removed_files += 1
            except OSError:
                continue

        return {"files": removed_files, "bytes": removed_bytes}

    @property
    def retention_days(self) -> int:
        return self._retention_days
