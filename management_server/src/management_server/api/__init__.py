"""API routes and exception handlers for the Management Server."""

from management_server.api.audit import router as audit_router
from management_server.api.commands import router as commands_router
from management_server.api.configsync import router as configsync_router
from management_server.api.discord import router as discord_router
from management_server.api.errors import register_exception_handlers
from management_server.api.heartbeat import router as heartbeat_router
from management_server.api.logs import router as logs_router
from management_server.api.notifications import router as notifications_router
from management_server.api.pairing import router as pairing_router
from management_server.api.policies import router as policies_router
from management_server.api.registration import router as registration_router
from management_server.api.routes import router
from management_server.api.routing import router as routing_router

__all__ = [
    "audit_router",
    "commands_router",
    "configsync_router",
    "discord_router",
    "heartbeat_router",
    "logs_router",
    "notifications_router",
    "pairing_router",
    "policies_router",
    "register_exception_handlers",
    "registration_router",
    "router",
    "routing_router",
]
