"""
Log compression — compresses rotated logs using gzip.

Compression is transparent: reads .gz files as if they were uncompressed.
"""

from __future__ import annotations

import gzip
import shutil
from pathlib import Path
from typing import Any

import structlog

from management_server.logging.exceptions import CompressionError

logger = structlog.get_logger("logging.compression")


class LogCompressor:
    """Compresses rotated log files using gzip."""

    def __init__(self, log_root: Path) -> None:
        self._log_root = log_root

    async def compress_file(self, path: Path) -> dict[str, Any]:
        """Compress a single log file with gzip."""
        if not path.exists():
            raise CompressionError(f"File not found: {path}")

        gz_path = path.with_suffix(path.suffix + ".gz")
        if gz_path.exists():
            logger.warning("Compressed file already exists, skipping", path=str(gz_path))
            return {"original": str(path), "compressed": str(gz_path), "skipped": True}

        original_size = path.stat().st_size
        try:
            with open(path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

            path.unlink()  # Remove original after compression
            compressed_size = gz_path.stat().st_size
            ratio = compressed_size / original_size if original_size > 0 else 0

            logger.info(
                "Log compressed",
                path=str(path),
                original=original_size,
                compressed=compressed_size,
                ratio=f"{ratio:.1%}",
            )

            return {
                "original": str(path),
                "compressed": str(gz_path),
                "original_bytes": original_size,
                "compressed_bytes": compressed_size,
                "ratio": round(ratio, 2),
                "skipped": False,
            }
        except OSError as e:
            raise CompressionError(f"Failed to compress {path}: {e}") from e

    async def compress_all(self, older_than_days: int = 1) -> list[dict[str, Any]]:
        """Compress all uncompressed rotated logs older than N days."""
        from datetime import UTC, datetime, timedelta

        results: list[dict[str, Any]] = []
        cutoff = datetime.now(tz=UTC) - timedelta(days=older_than_days)

        for ext in [".log", ".jsonl"]:
            for path in self._log_root.rglob(f"*{ext}"):
                if path.name.count("-") < 1:  # Skip current logs (no date)
                    continue
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
                if mtime < cutoff:
                    result = await self.compress_file(path)
                    results.append(result)

        return results

    @staticmethod
    def read_compressed(path: Path) -> str:
        """Read a compressed log file transparently."""
        try:
            with gzip.open(path, "rt") as f:
                return f.read()
        except OSError as e:
            raise CompressionError(f"Failed to read {path}: {e}") from e
