"""
Secure pairing token generation and hashing.

Uses Python's `secrets` module for cryptographically secure random values.
Only SHA-256 hashes of tokens are stored — plaintext is returned once and discarded.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import structlog

from management_server.pairing.exceptions import TokenGenerationError

logger = structlog.get_logger("pairing.generator")

TOKEN_BYTES = 64  # 64-byte cryptographically secure random value
TOKEN_ENCODING = "urlsafe"  # URL-safe base64 encoding


class PairingTokenGenerator:
    """Generates and hashes secure pairing tokens.

    Token generation:
        1. Generate 64 cryptographically secure random bytes
        2. Encode as URL-safe base64 (no padding)
        3. Compute SHA-256 hash of the encoded token
        4. Return (plaintext_token, token_hash)

    The plaintext token is returned to the caller and must be transmitted
    to the agent over a secure channel. Only the SHA-256 hash is persisted.
    """

    def __init__(self, token_ttl_minutes: int = 15) -> None:
        self._ttl = timedelta(minutes=token_ttl_minutes)

    def generate(self) -> tuple[str, str, datetime]:
        """Generate a new secure pairing token.

        Returns:
            (plaintext_token, token_hash, expires_at)
        """
        try:
            raw = secrets.token_bytes(TOKEN_BYTES)
            plaintext = self._encode(raw)
            token_hash = self._hash(plaintext)
            expires_at = datetime.now(tz=UTC) + self._ttl
            return plaintext, token_hash, expires_at
        except Exception as e:
            raise TokenGenerationError(f"Token generation failed: {e}") from e

    @staticmethod
    def _encode(raw: bytes) -> str:
        """Encode bytes as URL-safe base64 without padding."""
        import base64

        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    @staticmethod
    def _hash(token: str) -> str:
        """Compute SHA-256 hash of a token."""
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def verify_hash(token: str, expected_hash: str) -> bool:
        """Verify a token against its stored hash in constant time-ish."""
        computed = PairingTokenGenerator._hash(token)
        # Constant-time comparison to reduce timing side channels
        if len(computed) != len(expected_hash):
            return False
        result = 0
        for a, b in zip(computed.encode(), expected_hash.encode(), strict=False):
            result |= a ^ b
        return result == 0

    @staticmethod
    def generate_token_id() -> str:
        """Generate a random token identifier (not the secret itself)."""
        return secrets.token_hex(16)

    @property
    def ttl(self) -> timedelta:
        return self._ttl
