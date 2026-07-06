"""Detection Framework — modular plugin-based detection engine."""

from security_agent.detectors.base import Detector
from security_agent.detectors.capabilities import DetectorCapabilities
from security_agent.detectors.context import DetectorContext
from security_agent.detectors.exceptions import (
    DetectorError,
    DetectorExecutionError,
    DetectorInitializationError,
    DetectorNotFoundError,
    DetectorRegistrationError,
    InvalidDetectionResultError,
    UnsupportedEventError,
)
from security_agent.detectors.manager import DetectorManager
from security_agent.detectors.metrics import (
    DetectorMetricsCollector,
    DetectorMetricsSnapshot,
)
from security_agent.detectors.registry import DetectorRegistry
from security_agent.detectors.result import DetectionResult

__all__ = [
    "DetectionResult",
    "Detector",
    "DetectorCapabilities",
    "DetectorContext",
    "DetectorError",
    "DetectorExecutionError",
    "DetectorInitializationError",
    "DetectorManager",
    "DetectorMetricsCollector",
    "DetectorMetricsSnapshot",
    "DetectorNotFoundError",
    "DetectorRegistrationError",
    "DetectorRegistry",
    "InvalidDetectionResultError",
    "UnsupportedEventError",
]
