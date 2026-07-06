"""Threat Engine exceptions."""

from __future__ import annotations


class ThreatError(Exception):
    """Base exception for Threat Engine errors."""


class InvalidIncidentError(ThreatError):
    """Raised when an incident cannot be assessed."""


class ScoringError(ThreatError):
    """Raised when threat scoring fails."""


class AssessmentError(ThreatError):
    """Raised when assessment creation fails."""
