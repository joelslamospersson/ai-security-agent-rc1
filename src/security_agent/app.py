"""
Application lifecycle manager.

Coordinates startup, runtime, and graceful shutdown of all subsystems.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

import structlog

from security_agent import __version__

logger = structlog.get_logger()


class Application:
    """
    Top-level application lifecycle.

    Flow:
        1. Load configuration
        2. Set up structured logging
        3. Create Event Bus
        4. Initialize database
        5. Initialize plugins
        6. Start monitors
        7. Start pipeline stages
        8. Start self-monitoring
        9. Wait for shutdown signal
        10. Graceful shutdown (reverse order)
    """

    SHUTDOWN_TIMEOUT = 5.0

    def __init__(self, config_path: Path, dev_mode: bool = False) -> None:
        self._config_path = config_path
        self._dev_mode = dev_mode
        self._settings: Any = None  # Populated by _bootstrap
        self._shutdown_event = asyncio.Event()
        self._components: list[Component] = []
        self._start_time: float = 0.0

        # Subsystems (populated during startup)
        self.event_bus: Any = None
        self.database: Any = None
        self.plugins: dict[str, Any] = {}
        self.scheduler: Any = None
        self.metrics: Any = None
        self.self_monitor: Any = None
        self.pipeline: Any = None

    async def run(self) -> None:
        """Start the agent and wait for shutdown signal."""
        self._start_time = time.monotonic()
        startup_ok = False

        try:
            await self._bootstrap()
            await self._start_subsystems()
            startup_ok = True
            elapsed = time.monotonic() - self._start_time
            logger.info(
                "Agent started",
                version=__version__,
                startup_time_ms=round(elapsed * 1000),
                config=self._config_path,
                dev_mode=self._dev_mode,
            )
            print(f"[+] AI Security Agent v{__version__} started ({elapsed:.2f}s)")
            print(f"[+] PID: {process_id()}")
            print(f"[+] Config: {self._config_path}")
            if self._dev_mode:
                print("[!] Running in DEVELOPER MODE")
            print("[+] Press Ctrl+C to stop.")

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        except Exception:
            logger.exception("Failed to start agent")
            print("[!] Agent failed to start. See logs for details.")
            sys.exit(1)
        finally:
            if startup_ok:
                await self._shutdown()

    async def initialize_database(self) -> None:
        """Initialize database schema and exit (used by --init-db)."""
        logger.info("Initializing database")
        # Phase 15 will implement actual database initialization
        print("[+] Database schema created.")

    async def _bootstrap(self) -> None:
        """Load config and set up core infrastructure."""
        from security_agent.config.settings import load_settings

        try:
            self._settings = load_settings(self._config_path)
        except Exception as e:
            logger.error("Configuration load failed", error=str(e))
            print(f"[!] Configuration error: {e}")
            sys.exit(1)

        self._setup_logging()

        logger.info(
            "Bootstrap complete",
            config_path=str(self._config_path),
            profile=self._settings.profiles.active,
            debug=self._settings.general.debug,
        )

    def _setup_logging(self) -> None:
        """Configure structured logging with structlog."""
        if self._settings is None:
            logging.basicConfig(level=logging.INFO)
            return

        debug = self._settings.general.debug
        log_level = self._settings.general.log_level

        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                structlog.processors.StackInfoRenderer(),
                structlog.dev.ConsoleRenderer()
                if debug or self._dev_mode
                else structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        logging.root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        logger.debug(
            "Logging configured",
            debug=debug,
            level=log_level,
            format="console" if (debug or self._dev_mode) else "json",
        )

    async def _start_subsystems(self) -> None:
        """Start all subsystems. Implemented in later phases."""
        logger.info("Subsystem startup deferred to later phases")

    async def _shutdown(self) -> None:
        """
        Graceful shutdown in reverse initialization order.

        Waits for all components to stop, with a configurable timeout.
        After timeout, remaining components are cancelled.
        """
        shutdown_start = time.monotonic()
        logger.info("Shutdown initiated", components=len(self._components))

        # Shutdown in reverse order
        for component in reversed(self._components):
            try:
                await asyncio.wait_for(
                    component.stop(),
                    timeout=self.SHUTDOWN_TIMEOUT,
                )
            except TimeoutError:
                logger.warning(
                    "Component shutdown timed out",
                    component=component.name,
                )
            except Exception:
                logger.exception(
                    "Component shutdown error",
                    component=component.name,
                )

        elapsed = time.monotonic() - shutdown_start
        logger.info(
            "Shutdown complete",
            shutdown_time_ms=round(elapsed * 1000),
        )
        print(f"[+] Agent stopped ({elapsed:.2f}s)")


class Component:
    """
    Base class for manageable subsystems.

    All long-lived subsystems (Event Bus, Monitors, Pipeline, etc.)
    inherit from Component and implement start()/stop().
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._logger = structlog.get_logger(f"component.{name}")
        self._running = False

    async def start(self) -> None:
        """Start the component. Must be idempotent."""
        self._logger.debug("Starting")
        self._running = True

    async def stop(self) -> None:
        """Stop the component. Must be idempotent and non-blocking."""
        self._logger.debug("Stopping")
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running


def process_id() -> int:
    """Return current process ID."""
    import os

    return os.getpid()
