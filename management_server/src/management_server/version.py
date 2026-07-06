"""Version information for the Management Server."""

from __future__ import annotations

import os
from datetime import UTC, datetime

VERSION = "1.0.0"


def _get_git_commit() -> str:
    """Return the current git commit hash, or empty string if unavailable."""
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _get_build_timestamp() -> str:
    """Return the build timestamp, or current time if unavailable."""
    build_time = os.environ.get("BUILD_TIMESTAMP")
    if build_time:
        return build_time
    return datetime.now(tz=UTC).isoformat()


GIT_COMMIT = _get_git_commit()
BUILD_TIMESTAMP = _get_build_timestamp()


def get_version_info() -> dict[str, str]:
    """Return version information as a dictionary."""
    info: dict[str, str] = {
        "version": VERSION,
        "git_commit": GIT_COMMIT,
        "build_timestamp": BUILD_TIMESTAMP,
    }
    return info
