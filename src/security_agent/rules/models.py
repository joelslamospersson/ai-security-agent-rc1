"""
Rule data models — Rule, Condition, RuleMatch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _new_uuid() -> str:
    return str(uuid4())


class ConditionOp(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    REGEX = "regex"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    EXISTS = "exists"
    MISSING = "missing"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"


class LogicalOp(StrEnum):
    AND = "and"
    OR = "or"
    NOT = "not"


@dataclass(slots=True, frozen=True)
class Condition:
    field: str = ""
    operator: ConditionOp | None = None
    value: Any = None
    logical: LogicalOp | None = None
    conditions: tuple[Condition, ...] = ()


@dataclass(slots=True, frozen=True)
class Rule:
    id: str = ""
    name: str = ""
    description: str = ""
    enabled: bool = True
    version: str = "1.0"
    author: str = ""
    category: str = ""
    severity: int = 0
    confidence: int = 0
    threat_score: int = 0
    conditions: Condition = field(default_factory=Condition)
    ban_duration: int = 0
    alert_channel: str = ""

    def __post_init__(self) -> None:
        if not (0 <= self.severity <= 10):
            raise ValueError(f"Severity must be 0-10, got {self.severity}")
        if not (0 <= self.confidence <= 100):
            raise ValueError(f"Confidence must be 0-100, got {self.confidence}")
        if not (0 <= self.threat_score <= 100):
            raise ValueError(f"Threat score must be 0-100, got {self.threat_score}")


@dataclass(slots=True, frozen=True)
class RuleMatch:
    match_id: str = field(default_factory=_new_uuid)
    rule_id: str = ""
    rule_name: str = ""
    timestamp: datetime = field(default_factory=_now_utc)
    event_id: str = ""
    correlation_id: str = ""
    confidence: int = 0
    severity: int = 0
    threat_score: int = 0
    matched_conditions: tuple[str, ...] = ()
    evidence: str = ""

    def __post_init__(self) -> None:
        if not (0 <= self.confidence <= 100):
            raise ValueError(f"Confidence must be 0-100, got {self.confidence}")
        if not (0 <= self.severity <= 10):
            raise ValueError(f"Severity must be 0-10, got {self.severity}")
        if not (0 <= self.threat_score <= 100):
            raise ValueError(f"Threat score must be 0-100, got {self.threat_score}")
