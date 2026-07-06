"""
DetectorRegistry — manages registration, lookup, and enable/disable of detectors.
"""

from __future__ import annotations

from security_agent.detectors.base import Detector
from security_agent.detectors.exceptions import (
    DetectorNotFoundError,
    DetectorRegistrationError,
)


class DetectorRegistry:
    """Registry of detector instances.

    Supports registration, unregistration, lookup, enable/disable,
    and querying by supported event types.
    """

    def __init__(self) -> None:
        self._detectors: dict[str, Detector] = {}
        self._order: list[str] = []
        self._enabled: dict[str, bool] = {}

    def register(self, detector: Detector) -> None:
        """Register a detector.

        Raises DetectorRegistrationError on duplicate or empty name.
        """
        if not detector.name:
            raise DetectorRegistrationError("Detector name cannot be empty")
        if detector.name in self._detectors:
            raise DetectorRegistrationError(
                f"Detector '{detector.name}' is already registered"
            )
        self._detectors[detector.name] = detector
        self._order.append(detector.name)
        self._enabled[detector.name] = True

    def unregister(self, name: str) -> None:
        if name not in self._detectors:
            raise DetectorNotFoundError(f"Detector '{name}' not found")
        del self._detectors[name]
        self._order.remove(name)
        self._enabled.pop(name, None)

    def lookup(self, name: str) -> Detector:
        if name not in self._detectors:
            raise DetectorNotFoundError(f"Detector '{name}' not found")
        return self._detectors[name]

    def enable(self, name: str) -> None:
        if name not in self._detectors:
            raise DetectorNotFoundError(f"Detector '{name}' not found")
        self._enabled[name] = True
        self._detectors[name].enable()

    def disable(self, name: str) -> None:
        if name not in self._detectors:
            raise DetectorNotFoundError(f"Detector '{name}' not found")
        self._enabled[name] = False
        self._detectors[name].disable()

    def is_enabled(self, name: str) -> bool:
        return self._enabled.get(name, False)

    def validate(self) -> list[str]:
        """Validate all registered detectors. Returns list of warnings."""
        warnings: list[str] = []
        for name, detector in self._detectors.items():
            caps = detector.capabilities()
            if not caps.event_categories and not caps.event_types:
                warnings.append(
                    f"Detector '{name}' has no event types/categories declared"
                )
        return warnings

    def list_all(self) -> list[Detector]:
        return [self._detectors[name] for name in self._order]

    def list_enabled(self) -> list[Detector]:
        return [
            self._detectors[name]
            for name in self._order
            if self._enabled.get(name, False)
        ]

    def list_disabled(self) -> list[Detector]:
        return [
            self._detectors[name]
            for name in self._order
            if not self._enabled.get(name, False)
        ]

    @property
    def count(self) -> int:
        return len(self._detectors)

    @property
    def names(self) -> list[str]:
        return list(self._order)

    def clear(self) -> None:
        self._detectors.clear()
        self._order.clear()
        self._enabled.clear()
