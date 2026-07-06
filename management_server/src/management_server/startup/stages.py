"""
Startup initialization stages with dependency graph and fail-fast.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.audit.manager import AuditManager
from management_server.certificates.manager import CertificateManager
from management_server.certificates.store import CertificateStore
from management_server.commands.manager import CommandManager
from management_server.config.settings import Settings
from management_server.configsync.manager import ConfigSyncManager
from management_server.database.backend import DatabaseBackend
from management_server.discord.manager import DiscordManager
from management_server.health.emergency import EmergencyMode
from management_server.health.models import HealthState
from management_server.health.shutdown import ShutdownCoordinator
from management_server.health.startup import StartupValidator
from management_server.health.supervisor import HealthSupervisor
from management_server.heartbeat.manager import HeartbeatManager
from management_server.logging.manager import LoggingManager
from management_server.machines.manager import MachineManager
from management_server.notifications.manager import NotificationManager
from management_server.pairing.manager import PairingManager
from management_server.policies.manager import PolicyManager
from management_server.routing.manager import RoutingManager
from management_server.startup.models import Criticality, InitState, StartupReport, SubsystemStatus

logger = structlog.get_logger("startup.stages")


class InitStage:
    """A single initialization stage with dependencies."""

    def __init__(
        self,
        name: str,
        critical: Criticality = Criticality.CRITICAL,
        dependencies: list[str] | None = None,
    ) -> None:
        self.name = name
        self.critical = critical
        self.dependencies = dependencies or []
        self.state = InitState.PENDING
        self.error = ""

    def to_status(self) -> SubsystemStatus:
        return SubsystemStatus(
            name=self.name,
            state=self.state,
            critical=self.critical,
            error=self.error,
            dependencies=self.dependencies,
        )


STAGES: list[InitStage] = [
    InitStage("configuration", Criticality.CRITICAL),
    InitStage("logging", Criticality.CRITICAL, ["configuration"]),
    InitStage("database", Criticality.CRITICAL, ["configuration"]),
    InitStage("certificates", Criticality.CRITICAL, ["database"]),
    InitStage("machines", Criticality.NON_CRITICAL, ["database", "certificates"]),
    InitStage("pairing", Criticality.NON_CRITICAL, ["database", "machines"]),
    InitStage("heartbeat", Criticality.NON_CRITICAL, ["database"]),
    InitStage("policies", Criticality.NON_CRITICAL, ["database"]),
    InitStage("routing", Criticality.NON_CRITICAL, ["database"]),
    InitStage("notifications", Criticality.NON_CRITICAL, ["database"]),
    InitStage("audit", Criticality.NON_CRITICAL, ["database"]),
    InitStage("commands", Criticality.NON_CRITICAL, ["database"]),
    InitStage("configsync", Criticality.NON_CRITICAL, ["database"]),
    InitStage("discord", Criticality.NON_CRITICAL, ["database"]),
]


async def run_startup(app: FastAPI, settings: Settings) -> StartupReport:
    """Run the complete startup sequence with dependency resolution."""
    report = StartupReport()

    # Track managers in app state
    app.state.settings = settings
    app.state.emergency_mode = EmergencyMode()

    # Stage 1: Configuration
    _mark(report, "configuration", InitState.READY)

    # Stage 2: Logging (no deps)
    from management_server.utils.logging import configure_logging

    configure_logging(settings)
    logging_manager = LoggingManager()
    await logging_manager.initialize()
    app.state.logging_manager = logging_manager
    _mark(report, "logging", InitState.READY)

    # Stage 3: Database
    db = DatabaseBackend(settings)
    try:
        await db.initialize()
        app.state.db = db
        _mark(report, "database", InitState.READY)
    except Exception as e:
        error_msg = str(e)
        logger.critical("Database initialization failed", error=error_msg)
        _mark(report, "database", InitState.FAILED, error_msg)
        _fail_fast(report, "database")

    # Stage 4+: All DB-dependent managers
    if app.state.db is not None:
        try:
            async with db.session_factory() as session:
                await _init_db_managers(session, app, report)
        except Exception as e:
            logger.critical("Manager initialization failed", error=str(e))
    else:
        _skip_all_db_managers(report)

    # Health supervisor
    health_supervisor = HealthSupervisor()
    for name in STAGES:
        health_supervisor.register(name.name)
        status = report.stages.get(name.name)
        if status:
            state_map = {
                InitState.READY: HealthState.HEALTHY,
                InitState.FAILED: HealthState.FAILED,
                InitState.SKIPPED: HealthState.SHUTDOWN,
            }
            hs_state = state_map.get(status.state, HealthState.UNINITIALIZED)
            health_supervisor.update(name.name, hs_state, status.error)
    app.state.health_supervisor = health_supervisor

    # Startup validator
    app_state = {
        "db": app.state.db,
        "cert_manager": app.state.cert_manager,
        "settings": app.state.settings,
        "policy_manager": app.state.policy_manager,
        "routing_manager": app.state.routing_manager,
        "audit_manager": app.state.audit_manager,
        "logging_manager": app.state.logging_manager,
    }
    validator = StartupValidator()
    await validator.run_all(app_state)
    app.state.shutdown_coordinator = ShutdownCoordinator()

    # Save startup report for health endpoint
    app.state.startup_report = report

    return report


async def _init_db_managers(session: AsyncSession, app: FastAPI, report: StartupReport) -> None:
    """Initialize all DB-dependent managers."""
    cert_store = CertificateStore(session)
    cert_manager = CertificateManager(cert_store)
    await cert_manager.initialize()
    app.state.cert_manager = cert_manager
    _mark(report, "certificates", InitState.READY)

    machine_manager = MachineManager(session=session, cert_manager=cert_manager)
    await machine_manager.initialize()
    app.state.machine_manager = machine_manager
    _mark(report, "machines", InitState.READY)

    pairing_manager = PairingManager(session=session, registration_service=machine_manager.service)
    await pairing_manager.initialize()
    app.state.pairing_manager = pairing_manager
    _mark(report, "pairing", InitState.READY)

    heartbeat_manager = HeartbeatManager(session=session)
    await heartbeat_manager.initialize()
    app.state.heartbeat_manager = heartbeat_manager
    _mark(report, "heartbeat", InitState.READY)

    policy_manager = PolicyManager(session=session)
    await policy_manager.initialize()
    app.state.policy_manager = policy_manager
    _mark(report, "policies", InitState.READY)

    routing_manager = RoutingManager(session=session)
    await routing_manager.initialize()
    app.state.routing_manager = routing_manager
    _mark(report, "routing", InitState.READY)

    notification_manager = NotificationManager(session=session)
    await notification_manager.initialize()
    app.state.notification_manager = notification_manager
    _mark(report, "notifications", InitState.READY)

    audit_manager = AuditManager(session=session)
    await audit_manager.initialize()
    app.state.audit_manager = audit_manager
    _mark(report, "audit", InitState.READY)

    command_manager = CommandManager(session=session)
    await command_manager.initialize()
    app.state.command_manager = command_manager
    _mark(report, "commands", InitState.READY)

    configsync_manager = ConfigSyncManager(session=session)
    await configsync_manager.initialize()
    app.state.configsync_manager = configsync_manager
    _mark(report, "configsync", InitState.READY)

    discord_manager = DiscordManager(session=session)
    await discord_manager.initialize()
    app.state.discord_manager = discord_manager
    _mark(report, "discord", InitState.READY)

    logger.info("All DB-dependent managers initialized")


def _skip_all_db_managers(report: StartupReport) -> None:
    for name in [
        "certificates",
        "machines",
        "pairing",
        "heartbeat",
        "policies",
        "routing",
        "notifications",
        "audit",
        "commands",
        "configsync",
        "discord",
    ]:
        _mark(report, name, InitState.SKIPPED, "database unavailable")


def _mark(report: StartupReport, name: str, state: InitState, error: str = "") -> None:
    report.stages[name] = SubsystemStatus(
        name=name,
        state=state,
        critical=Criticality.CRITICAL
        if name in ("configuration", "logging", "database")
        else Criticality.NON_CRITICAL,
        error=error,
    )


def _fail_fast(report: StartupReport, failed_stage: str) -> None:
    """Print startup report and exit on critical failure."""
    from management_server.startup.report import print_startup_report

    print_startup_report(report)
    logger.critical("Startup aborted due to critical failure", stage=failed_stage)
    import sys

    sys.exit(1)
