"""
Routing models — immutable data structures for the Routing Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Any
from uuid import uuid4


class Priority(StrEnum):
    """Routing priority levels."""

    IMMEDIATE = auto()
    HIGH = auto()
    NORMAL = auto()
    LOW = auto()
    BULK = auto()

    @classmethod
    def from_str(cls, value: str) -> Priority:
        try:
            return cls[value.upper()]
        except KeyError:
            return cls.NORMAL


class Destination(StrEnum):
    """Supported destinations (no delivery implementation)."""

    DISCORD = auto()
    EMAIL = auto()
    WEBHOOK = auto()
    SYSLOG = auto()
    DASHBOARD = auto()
    ARCHIVE = auto()
    CONSOLE = auto()
    NONE = auto()

    @classmethod
    def is_valid(cls, name: str) -> bool:
        return name.upper() in {d.name for d in cls}


class Template(StrEnum):
    """Message template references (not rendered)."""

    MINIMAL = auto()
    DETAILED = auto()
    DISCORD_EMBED = auto()
    MARKDOWN = auto()
    JSON = auto()

    @classmethod
    def _missing_(cls, value: object) -> Template | None:
        if isinstance(value, str):
            for member in cls:
                if member.value == value.lower():
                    return member
        return None

    @classmethod
    def is_valid(cls, name: str) -> bool:
        return name.upper() in {t.name for t in cls}


@dataclass
class RateLimitProfile:
    """Rate limit configuration (not enforced)."""

    critical: str = "unlimited"
    high: str = "30/min"
    normal: str = "10/min"
    low: str = "1/min"
    bulk: str = "5/min"


@dataclass(frozen=True)
class RoutingDecision:
    """Immutable routing decision.

    Produced by the Routing Engine after evaluating all rules.
    Contains only routing metadata — no delivery logic.
    """

    decision_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    machine_id: str = ""
    event_type: str = ""
    destinations: list[str] = field(default_factory=list)
    priority: Priority = Priority.NORMAL
    template: Template = Template.DETAILED
    rate_limit_profile: str = "normal"
    retention_policy: str = "standard"
    matched_rule: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        machine_id: str,
        event_type: str,
        destinations: list[str],
        priority: Priority = Priority.NORMAL,
        template: Template = Template.DETAILED,
        rate_limit_profile: str = "normal",
        retention_policy: str = "standard",
        matched_rule: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        return cls(
            decision_id=uuid4().hex[:16],
            machine_id=machine_id,
            event_type=event_type,
            destinations=destinations,
            priority=priority,
            template=template,
            rate_limit_profile=rate_limit_profile,
            retention_policy=retention_policy,
            matched_rule=matched_rule,
            metadata=metadata or {},
        )


@dataclass
class RoutingRule:
    """A single routing rule definition."""

    name: str = ""
    description: str = ""
    event_types: list[str] = field(default_factory=lambda: ["*"])
    match_policy: str = ""
    match_machine_state: str = ""
    match_severity: str = ""
    match_feature_flags: dict[str, bool] = field(default_factory=dict)
    match_capabilities: list[str] = field(default_factory=list)
    match_environment: str = ""
    destinations: list[str] = field(default_factory=lambda: ["console"])
    priority: Priority = Priority.NORMAL
    template: Template = Template.DETAILED
    rate_limit_profile: str = "normal"
    retention_policy: str = "standard"
    enabled: bool = True


@dataclass
class RoutingProfile:
    """Rate limit and template profiles."""

    name: str = ""
    rate_limits: RateLimitProfile = field(default_factory=RateLimitProfile)
    default_destinations: list[str] = field(default_factory=lambda: ["console"])
    default_priority: Priority = Priority.NORMAL
    default_template: Template = Template.DETAILED
