"""
Log rotation — rotates log files daily.

Moves current.log → category-YYYY-MM-DD.log
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from management_server.logging.exceptions import RotationError
from management_server.logging.models import LOG_DIRECTORIES

logger = structlog.get_logger("logging.rotation")


class LogRotator:
    """Rotates log files by date."""

    def __init__(self, log_root: Path) -> None:
        self._log_root = log_root

    async def rotate_all(self) -> list[dict[str, Any]]:
        """Rotate all category log files."""
        results: list[dict[str, Any]] = []
        today = datetime.now(tz=UTC).strftime("%Y-%m-%d")

        for cat_dir in LOG_DIRECTORIES.values():
            for ext in [".log", ".jsonl"]:
                result = await self._rotate_file(cat_dir, ext, today)
                if result:
                    results.append(result)

        return results

    async def _rotate_file(self, category: str, ext: str, date_str: str) -> dict[str, Any] | None:
        """Rotate a single log file if it exists."""
        dir_path = self._log_root / category if ext == ".log" else self._log_root / "json"
        current_path = dir_path / f"{category}{ext}"
        rotated_path = dir_path / f"{category}-{date_str}{ext}"

        if not current_path.exists():
            return None

        try:
            # Only rotate if the current file has content
            if current_path.stat().st_size == 0:
                return None

            # If rotated file already exists, append current content
            if rotated_path.exists():
                content = current_path.read_text()
                with open(rotated_path, "a") as f:
                    f.write(content)
                current_path.write_text("")
            else:
                current_path.rename(rotated_path)

            logger.info("Log rotated", category=category, rotated=str(rotated_path))
            return {
                "category": category,
                "from": str(current_path),
                "to": str(rotated_path),
            }
        except OSError as e:
            raise RotationError(f"Failed to rotate {category}: {e}") from e
