"""
Shared models for the Integration Test Harness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any


class ScenarioStatus(StrEnum):
    PENDING = auto()
    RUNNING = auto()
    PASSED = auto()
    FAILED = auto()
    ERROR = auto()


class AssertionResult(StrEnum):
    PASS = auto()
    FAIL = auto()
    SKIP = auto()


@dataclass
class ScenarioEvent:
    """A recorded event during scenario execution."""

    timestamp: float = 0.0
    event_type: str = ""
    source: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Assertion:
    """A single assertion check."""

    name: str = ""
    result: AssertionResult = AssertionResult.PASS
    message: str = ""
    expected: str = ""
    actual: str = ""


@dataclass
class ScenarioResult:
    """Result of a single scenario run."""

    name: str = ""
    status: ScenarioStatus = ScenarioStatus.PENDING
    assertions: list[Assertion] = field(default_factory=list)
    events: list[ScenarioEvent] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    error: str = ""
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class HarnessReport:
    """Complete harness run report."""

    timestamp: str = ""
    scenarios: list[ScenarioResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    total_assertions: int = 0
    passed_assertions: int = 0
    failed_assertions: int = 0
    benchmark: dict[str, Any] = field(default_factory=dict)
