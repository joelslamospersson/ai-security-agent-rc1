"""
Init status models — subsystem initialization states.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any


class InitState(StrEnum):
    """Initialization state of a subsystem."""

    PENDING = auto()
    INITIALIZING = auto()
    READY = auto()
    FAILED = auto()
    SKIPPED = auto()


class Criticality(StrEnum):
    """Whether a subsystem failure should abort startup."""

    CRITICAL = auto()
    NON_CRITICAL = auto()


@dataclass
class SubsystemStatus:
    """Status of a single subsystem during initialization."""

    name: str = ""
    state: InitState = InitState.PENDING
    critical: Criticality = Criticality.CRITICAL
    error: str = ""
    dependencies: list[str] = field(default_factory=list)


@dataclass
class StartupReport:
    """Complete startup report."""

    stages: dict[str, SubsystemStatus] = field(default_factory=dict)
    aborted: bool = False

    def set_state(self, name: str, state: InitState, error: str = "") -> None:
        if name in self.stages:
            self.stages[name].state = state
            self.stages[name].error = error

    @property
    def all_ready(self) -> bool:
        return all(s.state == InitState.READY for s in self.stages.values())

    @property
    def any_failed(self) -> bool:
        return any(s.state == InitState.FAILED for s in self.stages.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "aborted": self.aborted,
            "stages": {
                name: {"state": s.state.value, "critical": s.critical.value, "error": s.error}
                for name, s in self.stages.items()
            },
        }
