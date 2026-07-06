"""
Shared test fixtures for AI Security Agent.

Provides:
- Configured structlog for test output
- Temporary directory for test data
- Application instance for integration tests
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import structlog


@pytest.fixture(scope="session", autouse=True)
def _configure_test_logging() -> None:
    """Configure structlog for test output (quiet, console-friendly)."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Temporary directory for test data files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
async def app_instance(tmp_data_dir: Path) -> AsyncGenerator[Any, None]:
    """Create a minimal Application instance for integration tests."""
    from security_agent.app import Application

    app = Application(
        config_path=tmp_data_dir / "config.yaml",
        dev_mode=True,
    )
    try:
        yield app
    finally:
        await app._shutdown()
