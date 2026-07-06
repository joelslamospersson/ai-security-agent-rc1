"""Reputation Engine exceptions."""

from __future__ import annotations


class ReputationError(Exception):
    """Base exception for Reputation Engine errors."""


class EntityNotFoundError(ReputationError):
    """Raised when an entity is not found."""


class InvalidEntityError(ReputationError):
    """Raised when an entity type/value is invalid."""


class ScoringError(ReputationError):
    """Raised when reputation scoring fails."""


class DecayError(ReputationError):
    """Raised when decay calculation fails."""
