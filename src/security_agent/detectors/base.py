"""
Abstract Detector interface.

Every detector in the project inherits from Detector and implements:
- initialize()
- analyze(event, context) → list[DetectionResult]
- shutdown()
- capabilities()

The framework knows nothing about individual detector implementations.
Detectors never interact with firewall, database, reputation, or alerts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from security_agent.detectors.capabilities import DetectorCapabilities
from security_agent.detectors.context import DetectorContext
from security_agent.detectors.result import DetectionResult
from security_agent.events.models import BaseEvent


class Detector(ABC):
    """Abstract base for all detection modules.

    Lifecycle:
        initialize()   → prepare resources
        analyze()      → examine events, return results
        shutdown()     → release resources
        capabilities() → declare supported events
    """

    def __init__(self, detector_id: str, name: str) -> None:
        self._detector_id = detector_id
        self._name = name
        self._initialized = False
        self._enabled = True

    @property
    def detector_id(self) -> str:
        return self._detector_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    async def initialize(self) -> None:
        """Prepare detector resources. Called once at startup."""
        self._initialized = True

    @abstractmethod
    async def analyze(
        self,
        event: BaseEvent,
        context: DetectorContext,
    ) -> list[DetectionResult]:
        """Analyze an event and return detection results.

        Args:
            event: The normalized event to analyze.
            context: Immutable context for this analysis call.

        Returns:
            List of DetectionResults (may be empty).
        """

    async def shutdown(self) -> None:
        """Release detector resources. Called once at shutdown."""
        self._initialized = False

    @abstractmethod
    def capabilities(self) -> DetectorCapabilities:
        """Declare what event types this detector can process."""
