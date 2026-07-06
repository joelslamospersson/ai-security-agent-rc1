"""
FastAPI application factory for the Management Server.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from management_server.api import (
    audit_router,
    commands_router,
    configsync_router,
    discord_router,
    heartbeat_router,
    logs_router,
    notifications_router,
    pairing_router,
    policies_router,
    register_exception_handlers,
    registration_router,
    router,
    routing_router,
)
from management_server.api.routes import set_startup_time
from management_server.config.settings import Settings, get_settings
from management_server.version import VERSION
from management_server.startup.report import print_startup_report
from management_server.startup.stages import run_startup

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown."""
    settings = get_settings()

    # Run staged startup
    report = await run_startup(app, settings)

    # Print startup report
    print_startup_report(report)
    set_startup_time()

    logger.info("Management Server starting", log_level=settings.log_level)

    yield

    # Graceful shutdown
    if app.state.db is not None:
        await app.state.db.shutdown()
    for attr in [
        "cert_manager",
        "machine_manager",
        "pairing_manager",
        "heartbeat_manager",
        "policy_manager",
        "routing_manager",
        "notification_manager",
        "audit_manager",
        "command_manager",
        "configsync_manager",
        "discord_manager",
        "logging_manager",
    ]:
        setattr(app.state, attr, None)
    app.state.db = None
    logger.info("Management Server shutting down")


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()
    app = FastAPI(
        title="AI Security Management Server",
        version=VERSION,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    register_exception_handlers(app)
    app.include_router(router)
    app.include_router(registration_router)
    app.include_router(pairing_router)
    app.include_router(heartbeat_router)
    app.include_router(policies_router)
    app.include_router(routing_router)
    app.include_router(notifications_router)
    app.include_router(audit_router)
    app.include_router(commands_router)
    app.include_router(configsync_router)
    app.include_router(discord_router)
    app.include_router(logs_router)
    app.state.settings = settings
    return app
