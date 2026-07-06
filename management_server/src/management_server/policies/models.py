"""
Policy models — data structures for the Policy Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class FeatureFlags:
    """Feature flags managed through policies."""

    discord: bool = False
    geoip: bool = False
    docker: bool = False
    web_dashboard: bool = False
    remote_commands: bool = False
    experimental: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {
            "discord": self.discord,
            "geoip": self.geoip,
            "docker": self.docker,
            "web_dashboard": self.web_dashboard,
            "remote_commands": self.remote_commands,
            "experimental": self.experimental,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureFlags:
        return cls(
            discord=bool(data.get("discord", False)),
            geoip=bool(data.get("geoip", False)),
            docker=bool(data.get("docker", False)),
            web_dashboard=bool(data.get("web_dashboard", False)),
            remote_commands=bool(data.get("remote_commands", False)),
            experimental=bool(data.get("experimental", False)),
        )


@dataclass
class Policy:
    """A single policy definition — the source of truth for operational behaviour."""

    name: str = ""
    description: str = ""
    version: str = "1"
    parent: str = ""  # Single inheritance parent
    checksum: str = ""

    # Operational settings
    heartbeat_interval_seconds: int = 30
    notification_retention_days: int = 30
    log_retention_days: int = 90
    ip_masking_enabled: bool = True
    maintenance_mode: bool = False
    allowed_protocol_versions: list[str] = field(default_factory=lambda: ["1.0"])

    # Feature flags
    feature_flags: FeatureFlags = field(default_factory=FeatureFlags)

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    # Raw YAML data for future extension
    raw_yaml: dict[str, Any] = field(default_factory=dict)

    @property
    def is_default(self) -> bool:
        return self.name == "default"

    @property
    def has_parent(self) -> bool:
        return bool(self.parent)


@dataclass
class PolicyAssignment:
    """Assignment of a policy to a machine."""

    machine_uuid: str = ""
    policy_name: str = ""
    assigned_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    assigned_by: str = "system"


@dataclass
class PolicyOverride:
    """Machine-specific override of a policy value."""

    machine_uuid: str = ""
    policy_name: str = ""
    key: str = ""
    value: str = ""
    original_value: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    created_by: str = "admin"
