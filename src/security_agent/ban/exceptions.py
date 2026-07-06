"""Ban Engine exceptions."""

from __future__ import annotations


class BanError(Exception):
    """Base exception for Ban Engine errors."""


class InvalidDecisionError(BanError):
    """Raised when a ban decision cannot be formed."""


class PolicyNotFoundError(BanError):
    """Raised when a ban policy is not found."""


class EscalationError(BanError):
    """Raised when escalation calculation fails."""


class WhitelistError(BanError):
    """Raised on invalid whitelist operations."""
