"""
Config sync validator — validates packages and version compatibility.
"""

from __future__ import annotations

import structlog

from management_server.configsync.exceptions import (
    IntegrityError,
    PackageValidationError,
    VersionMismatchError,
)
from management_server.configsync.models import ConfigurationPackage, PackageType

logger = structlog.get_logger("configsync.validator")

VALID_PACKAGE_TYPES = {t.value for t in PackageType}


class PackageValidator:
    """Validates configuration packages and version compatibility."""

    @staticmethod
    def validate_new(
        package_type: str,
        version: str,
        payload: str = "",
        format_type: str = "full",
    ) -> list[str]:
        """Validate a new package request. Returns list of errors."""
        errors: list[str] = []

        if not package_type:
            errors.append("package_type is required")
        elif package_type not in VALID_PACKAGE_TYPES:
            errors.append(f"Unknown package type: '{package_type}'")

        if not version:
            errors.append("version is required")

        if format_type not in ("full", "delta"):
            errors.append(f"Invalid format: '{format_type}'")

        if format_type == "delta" and not payload:
            errors.append("Delta packages require a payload")

        return errors

    @staticmethod
    def validate_and_raise(
        package_type: str,
        version: str,
        payload: str = "",
        format_type: str = "full",
    ) -> None:
        errors = PackageValidator.validate_new(package_type, version, payload, format_type)
        if errors:
            raise PackageValidationError(errors[0])

    @staticmethod
    def verify_integrity(package: ConfigurationPackage) -> None:
        """Verify package checksum integrity."""
        if not package.verify_integrity():
            raise IntegrityError(f"Package {package.package_id} checksum mismatch")

    @staticmethod
    def verify_agent_compatibility(
        package: ConfigurationPackage,
        agent_version: str,
    ) -> None:
        """Verify agent version meets minimum requirements."""
        if (
            package.minimum_agent_version
            and agent_version
            and agent_version < package.minimum_agent_version
        ):
            raise VersionMismatchError(agent_version, package.minimum_agent_version)

    @staticmethod
    def get_available_for_agent(
        packages: list[ConfigurationPackage],
        agent_version: str,
        current_versions: dict[str, str] | None = None,
    ) -> list[ConfigurationPackage]:
        """Get packages that are available for an agent."""
        current = current_versions or {}
        available: list[ConfigurationPackage] = []

        for pkg in packages:
            if pkg.state.value not in ("published", "available"):
                continue
            if pkg.minimum_agent_version and agent_version < pkg.minimum_agent_version:
                continue
            # Skip if agent already has this version or newer
            cur_ver = current.get(pkg.package_type.value, "0")
            if cur_ver >= pkg.version:
                continue
            available.append(pkg)

        return available
