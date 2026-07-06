"""
Config sync models — immutable ConfigurationPackage, package types, lifecycle states.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Any
from uuid import uuid4


class PackageType(StrEnum):
    """Types of configuration packages."""

    CONFIGURATION = auto()
    RULES = auto()
    POLICIES = auto()
    FEATURE_FLAGS = auto()
    GEOIP = auto()
    CERTIFICATES = auto()


class PackageState(StrEnum):
    """Package lifecycle states."""

    CREATED = auto()
    SIGNED = auto()
    PUBLISHED = auto()
    AVAILABLE = auto()
    SUPERSEDED = auto()
    ARCHIVED = auto()


class PackageFormat(StrEnum):
    """Package format types."""

    FULL = auto()
    DELTA = auto()


@dataclass(frozen=True)
class ConfigurationPackage:
    """Immutable configuration package.

    Never modified after creation. State changes create new lifecycle records.
    """

    package_id: str = ""
    package_type: PackageType = PackageType.CONFIGURATION
    version: str = "1"
    format: PackageFormat = PackageFormat.FULL
    state: PackageState = PackageState.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    checksum: str = ""
    signature: str = ""
    payload: str = ""
    metadata_json: str = "{}"
    minimum_agent_version: str = ""
    rollback_version: str = ""
    base_package_id: str = ""

    @classmethod
    def create(
        cls,
        package_type: PackageType | str,
        version: str = "1",
        payload: str = "",
        metadata: dict[str, Any] | None = None,
        minimum_agent_version: str = "",
        rollback_version: str = "",
        format_type: PackageFormat = PackageFormat.FULL,
        base_package_id: str = "",
    ) -> ConfigurationPackage:
        """Create a new configuration package with checksum."""
        package_id = uuid4().hex[:16]
        ts = datetime.now(tz=UTC)
        meta_json = json.dumps(metadata or {}, default=str, sort_keys=True)

        if isinstance(package_type, str):
            package_type = PackageType(package_type)

        content = (
            f"{package_id}|{package_type.value}|{version}|{ts.isoformat()}|{payload}|{meta_json}"
        )
        checksum = hashlib.sha256(content.encode()).hexdigest()

        return cls(
            package_id=package_id,
            package_type=package_type,
            version=version,
            format=format_type,
            state=PackageState.CREATED,
            created_at=ts,
            checksum=checksum,
            payload=payload,
            metadata_json=meta_json,
            minimum_agent_version=minimum_agent_version,
            rollback_version=rollback_version,
            base_package_id=base_package_id,
        )

    def compute_checksum(self) -> str:
        """Recompute checksum for integrity verification."""
        content = f"{self.package_id}|{self.package_type.value}|{self.version}|{self.created_at.isoformat()}|{self.payload}|{self.metadata_json}"
        return hashlib.sha256(content.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify package checksum."""
        return self.checksum == self.compute_checksum()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for heartbeat advertisement."""
        return {
            "package_id": self.package_id,
            "package_type": self.package_type.value,
            "version": self.version,
            "format": self.format.value,
            "state": self.state.value,
            "checksum": self.checksum,
            "minimum_agent_version": self.minimum_agent_version,
            "rollback_version": self.rollback_version,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class MachinePackageVersion:
    """Tracks the version state of a machine for each package type."""

    machine_uuid: str = ""
    package_type: PackageType = PackageType.CONFIGURATION
    current_version: str = "0"
    desired_version: str = ""
    last_sync_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


# Need json import at module level
import json  # noqa: E402
