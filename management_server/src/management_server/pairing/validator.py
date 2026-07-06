"""
Pairing token validator — validates token authenticity, expiry, and replay status.

All validation is stateless: state lookups (hash, expiry, consumption) are
handled by the PairingService which owns the repository.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from management_server.pairing.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    ReplayAttackError,
    TokenRevokedError,
)
from management_server.pairing.generator import PairingTokenGenerator
from management_server.pairing.models import TokenState

logger = structlog.get_logger("pairing.validator")


class PairingTokenValidator:
    """Validates pairing tokens against security constraints.

    Checks performed (in order):
        1. Token hash matches a known record
        2. Token has not expired
        3. Token has not been consumed (replay protection)
        4. Token has not been revoked
    """

    @staticmethod
    def validate_token(
        token: str,
        token_hash: str,
        status: TokenState,
        expires_at: datetime,
    ) -> None:
        """Validate a token against all security constraints.

        Raises typed exceptions for each failure mode.
        """
        # 1. Hash verification
        if not PairingTokenGenerator.verify_hash(token, token_hash):
            raise InvalidTokenError("Token hash mismatch")

        # 2. Expiration check
        now = datetime.now(tz=UTC)
        if now > expires_at:
            raise ExpiredTokenError()

        # 3. Replay / consumption check
        if status == TokenState.CONSUMED:
            raise ReplayAttackError("Token has already been consumed")
        if status == TokenState.EXPIRED:
            raise ExpiredTokenError()

        # 4. Revocation check
        if status == TokenState.REVOKED:
            raise TokenRevokedError()

    @staticmethod
    def validate_for_consumption(
        token: str,
        token_hash: str,
        status: TokenState,
        expires_at: datetime,
    ) -> None:
        """Stricter validation for token consumption.

        Only ISSUED or PENDING tokens can be consumed.
        """
        PairingTokenValidator.validate_token(token, token_hash, status, expires_at)

        if status not in (TokenState.ISSUED, TokenState.PENDING):
            if status == TokenState.CONSUMED:
                raise ReplayAttackError("Token has already been consumed")
            if status == TokenState.REVOKED:
                raise TokenRevokedError()
            raise InvalidTokenError(f"Token in state {status.value} cannot be consumed")
