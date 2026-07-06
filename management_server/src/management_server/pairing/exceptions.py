"""
Pairing exceptions — typed error hierarchy for the secure pairing protocol.
"""

from __future__ import annotations


class PairingError(Exception):
    """Base exception for all pairing-related errors."""


class InvalidTokenError(PairingError):
    """Token is malformed or does not exist."""

    def __init__(self, detail: str = "Invalid token") -> None:
        super().__init__(detail)


class ExpiredTokenError(PairingError):
    """Token has exceeded its time-to-live."""

    def __init__(self, detail: str = "Token has expired") -> None:
        super().__init__(detail)


class ReplayAttackError(PairingError):
    """Token has already been consumed (replay attempt detected)."""

    def __init__(self, detail: str = "Token has already been consumed") -> None:
        super().__init__(detail)


class TokenConsumedError(PairingError):
    """Token was already consumed."""

    def __init__(self, detail: str = "Token has already been used") -> None:
        super().__init__(detail)


class TokenRevokedError(PairingError):
    """Token was revoked before use."""

    def __init__(self, detail: str = "Token has been revoked") -> None:
        super().__init__(detail)


class TokenGenerationError(PairingError):
    """Token generation failure."""


class InvalidTransitionError(PairingError):
    """Illegal pairing token state transition."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition token from {current} to {target}")


class PairingRepositoryError(PairingError):
    """Database error during pairing operations."""
