"""
Startup validation — verifies all subsystems before allowing full operation.

Aborts startup if critical validation fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger("health.startup")


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    name: str = ""
    passed: bool = False
    critical: bool = True
    message: str = ""


@dataclass
class StartupValidationReport:
    """Complete startup validation report."""

    results: list[ValidationResult] = field(default_factory=list)
    all_passed: bool = True
    critical_failures: list[str] = field(default_factory=list)


class StartupValidator:
    """Validates all subsystems at startup."""

    def __init__(self) -> None:
        self._results: list[ValidationResult] = []

    async def run_all(self, app_state: dict[str, Any]) -> StartupValidationReport:
        """Run all startup validations."""
        self._results = []

        await self._check_database(app_state)
        await self._check_certificates(app_state)
        await self._check_config(app_state)
        await self._check_policies(app_state)
        await self._check_routing(app_state)
        await self._check_audit(app_state)
        await self._check_logging(app_state)

        report = StartupValidationReport(results=list(self._results))
        passed_count = sum(1 for r in self._results if r.passed)
        report.all_passed = passed_count == len(self._results)
        report.critical_failures = [r.name for r in self._results if not r.passed and r.critical]

        if report.critical_failures:
            logger.error(
                "Startup validation failed — critical checks failed",
                failures=report.critical_failures,
            )
        else:
            logger.info(
                "Startup validation passed",
                checks=len(self._results),
                passed=passed_count,
            )

        return report

    async def _check_database(self, state: dict[str, Any]) -> None:
        db = state.get("db")
        if db is not None and getattr(db, "is_initialized", False):
            self._results.append(ValidationResult("database", True, True, "Connected"))
        else:
            self._results.append(
                ValidationResult("database", False, True, "Not connected — critical")
            )

    async def _check_certificates(self, state: dict[str, Any]) -> None:
        cert = state.get("cert_manager")
        if cert is not None and getattr(cert, "is_initialized", False):
            self._results.append(ValidationResult("certificates", True, True, "Initialized"))
        else:
            self._results.append(
                ValidationResult("certificates", False, True, "Not initialized — critical")
            )

    async def _check_config(self, state: dict[str, Any]) -> None:
        settings = state.get("settings")
        if settings is not None:
            self._results.append(ValidationResult("configuration", True, True, "Loaded"))
        else:
            self._results.append(
                ValidationResult("configuration", False, True, "Not loaded — critical")
            )

    async def _check_policies(self, state: dict[str, Any]) -> None:
        policies = state.get("policy_manager")
        if policies is not None and getattr(policies, "is_initialized", False):
            self._results.append(ValidationResult("policies", True, False, "Loaded"))
        else:
            self._results.append(ValidationResult("policies", False, False, "Not loaded"))

    async def _check_routing(self, state: dict[str, Any]) -> None:
        routing = state.get("routing_manager")
        if routing is not None and getattr(routing, "is_initialized", False):
            self._results.append(ValidationResult("routing", True, False, "Loaded"))
        else:
            self._results.append(ValidationResult("routing", False, False, "Not loaded"))

    async def _check_audit(self, state: dict[str, Any]) -> None:
        audit = state.get("audit_manager")
        if audit is not None and getattr(audit, "is_initialized", False):
            self._results.append(ValidationResult("audit", True, False, "Ready"))
        else:
            self._results.append(ValidationResult("audit", False, False, "Not ready"))

    async def _check_logging(self, state: dict[str, Any]) -> None:
        logging_mgr = state.get("logging_manager")
        if logging_mgr is not None and getattr(logging_mgr, "is_initialized", False):
            self._results.append(ValidationResult("logging", True, False, "Ready"))
        else:
            self._results.append(ValidationResult("logging", False, False, "Not ready"))
