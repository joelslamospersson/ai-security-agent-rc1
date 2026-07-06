"""
Pairing service — orchestrates the secure pairing protocol.

Coordinates token generation, validation, consumption, expiration,
and registration integration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from management_server.machines.service import RegistrationService
from management_server.pairing.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    PairingError,
    ReplayAttackError,
    TokenConsumedError,
    TokenGenerationError,
    TokenRevokedError,
)
from management_server.pairing.generator import PairingTokenGenerator
from management_server.pairing.metrics import PairingMetricsCollector
from management_server.pairing.models import TokenState, TokenStateMachine
from management_server.pairing.repository import PairingRepository
from management_server.pairing.schemas import (
    PairingConsumeRequest,
    PairingConsumeResponse,
    PairingTokenCreateRequest,
    PairingTokenResponse,
    PairingValidateRequest,
    PairingValidateResponse,
)
from management_server.pairing.validator import PairingTokenValidator

logger = structlog.get_logger("pairing.service")


class PairingService:
    """Secure pairing protocol service.

    Manages the full lifecycle of pairing tokens from generation
    through consumption, with replay protection and registration integration.
    """

    def __init__(
        self,
        repository: PairingRepository,
        generator: PairingTokenGenerator | None = None,
        metrics: PairingMetricsCollector | None = None,
        registration_service: RegistrationService | None = None,
    ) -> None:
        self._repository = repository
        self._generator = generator or PairingTokenGenerator()
        self._metrics = metrics or PairingMetricsCollector()
        self._registration_service = registration_service

    async def create_token(self, request: PairingTokenCreateRequest) -> PairingTokenResponse:
        """Generate and persist a new pairing token.

        The plaintext token is returned exactly once and never stored.
        Only its SHA-256 hash is persisted.
        """
        try:
            plaintext, token_hash, expires_at = self._generator.generate()
        except TokenGenerationError:
            raise

        token_id = PairingTokenGenerator.generate_token_id()

        record = await self._repository.create_token(
            token_id=token_id,
            token_hash=token_hash,
            expires_at=expires_at,
            creator=request.creator,
            machine_uuid=request.machine_uuid,
            audit_reference=request.audit_reference,
        )

        self._metrics.token_generated()

        logger.info(
            "Pairing token generated",
            token_id=token_id,
            creator=request.creator,
            expires_at=expires_at.isoformat(),
        )

        return PairingTokenResponse(
            token=plaintext,
            token_id=token_id,
            expires_at=expires_at,
            status=TokenState(record["status"]),
        )

    async def validate_token(self, request: PairingValidateRequest) -> PairingValidateResponse:
        """Validate a pairing token without consuming it."""
        try:
            token_hash = PairingTokenGenerator._hash(request.token)

            record = await self._repository.get_by_token_hash(token_hash)
            if record is None:
                self._metrics.validation_failure()
                return PairingValidateResponse(
                    valid=False,
                    token_id="",
                    status=TokenState.UNUSED,
                    message="Token not found",
                )

            PairingTokenValidator.validate_token(
                token=request.token,
                token_hash=token_hash,
                status=TokenState(record["status"]),
                expires_at=_parse_dt(record["expires_at"]),
            )

            # If token is in ISSUED state, transition to PENDING
            current_status = TokenState(record["status"])
            if current_status == TokenState.ISSUED:
                TokenStateMachine.validate_transition(TokenState.ISSUED, TokenState.PENDING)
                record = await self._repository.update_status(
                    record["token_id"],
                    TokenState.PENDING,
                    machine_uuid=request.machine_uuid,
                )

            logger.info(
                "Pairing token validated",
                token_id=record["token_id"],
                machine_uuid=request.machine_uuid,
            )

            return PairingValidateResponse(
                valid=True,
                token_id=record["token_id"],
                status=TokenState(record["status"]),
                message="Token is valid",
            )

        except (
            InvalidTokenError,
            ExpiredTokenError,
            TokenConsumedError,
            TokenRevokedError,
            ReplayAttackError,
        ) as e:
            self._metrics.validation_failure()
            if isinstance(e, ReplayAttackError):
                self._metrics.replay_attempt()
            return PairingValidateResponse(
                valid=False,
                token_id="",
                status=TokenState.UNUSED,
                message=str(e),
            )

    async def consume_token(self, request: PairingConsumeRequest) -> PairingConsumeResponse:
        """Consume a pairing token and initiate registration."""
        token_hash = PairingTokenGenerator._hash(request.token)

        record = await self._repository.get_by_token_hash(token_hash)
        if record is None:
            self._metrics.validation_failure()
            raise InvalidTokenError("Token not found")

        # Strict validation for consumption
        PairingTokenValidator.validate_for_consumption(
            token=request.token,
            token_hash=token_hash,
            status=TokenState(record["status"]),
            expires_at=_parse_dt(record["expires_at"]),
        )

        current_status = TokenState(record["status"])
        TokenStateMachine.validate_transition(current_status, TokenState.CONSUMED)

        # Update to consumed
        await self._repository.update_status(
            record["token_id"],
            TokenState.CONSUMED,
            machine_uuid=request.machine_uuid,
        )

        self._metrics.token_consumed()

        logger.info(
            "Pairing token consumed",
            token_id=record["token_id"],
            machine_uuid=request.machine_uuid,
        )

        return PairingConsumeResponse(
            paired=True,
            machine_uuid=request.machine_uuid,
            token_id=record["token_id"],
            message="Token consumed — registration can proceed",
        )

    async def expire_stale_tokens(self) -> int:
        """Expire all pending tokens past TTL."""
        count: int = await self._repository.expire_pending_tokens()
        count += await self._repository.expire_unused_tokens()
        if count:
            self._metrics.token_expired()
            logger.info("Stale pairing tokens expired", count=count)
        return count

    async def revoke_token(self, token_id: str) -> dict[str, Any]:
        """Revoke a token by its token_id."""
        record = await self._repository.get_by_token_id(token_id)
        current_status = TokenState(record["status"])
        if current_status in (TokenState.CONSUMED, TokenState.EXPIRED):
            raise PairingError(f"Cannot revoke token in state {current_status.value}")

        TokenStateMachine.validate_transition(current_status, TokenState.REVOKED)
        updated: dict[str, Any] = await self._repository.revoke_token(token_id)
        self._metrics.token_revoked()

        logger.info("Pairing token revoked", token_id=token_id)
        return updated

    async def get_token_info(self, token_id: str) -> dict[str, Any]:
        """Get public info about a token (no hash, no plaintext)."""
        record = await self._repository.get_by_token_id(token_id)
        # Strip sensitive fields
        result: dict[str, Any] = dict(record)
        result.pop("token_hash", None)
        result.pop("id", None)  # internal PK
        return result

    async def list_tokens(
        self,
        status: TokenState | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List tokens with pagination (no hashes exposed)."""
        tokens, total = await self._repository.list_tokens(
            status=status, limit=limit, offset=offset
        )
        # Strip sensitive fields
        safe_tokens: list[dict[str, Any]] = []
        for t in tokens:
            safe = dict(t)
            safe.pop("token_hash", None)
            safe.pop("id", None)
            safe_tokens.append(safe)

        return {
            "tokens": safe_tokens,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_metrics(self) -> dict[str, int]:
        """Get pairing metrics snapshot."""
        counts = await self._repository.count_by_status()
        total = sum(counts.values())
        active = counts.get(TokenState.ISSUED.value, 0) + counts.get(TokenState.PENDING.value, 0)
        snapshot = self._metrics.snapshot(active_tokens=active, total_tokens=total)
        return {
            "tokens_generated": snapshot.tokens_generated,
            "tokens_consumed": snapshot.tokens_consumed,
            "tokens_expired": snapshot.tokens_expired,
            "tokens_revoked": snapshot.tokens_revoked,
            "validation_failures": snapshot.validation_failures,
            "replay_attempts": snapshot.replay_attempts,
            "active_tokens": active,
            "total_tokens": total,
        }


def _parse_dt(value: object) -> datetime:
    """Parse a datetime value that may be a string or datetime object."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            from dateutil import parser as dateutil_parser

            parsed = dateutil_parser.parse(value)
            if isinstance(parsed, datetime):
                return parsed
        except Exception:
            pass
    return datetime.now(tz=UTC)
