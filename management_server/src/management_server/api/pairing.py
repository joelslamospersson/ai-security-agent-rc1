"""
Pairing API endpoints for the Management Server.

POST /api/v1/pairing                   — Generate a pairing token
POST /api/v1/pairing/validate          — Validate a pairing token
POST /api/v1/pairing/consume           — Consume a pairing token
GET  /api/v1/pairing/{id}              — Get pairing token info

Authentication is isolated behind interfaces for later implementation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from management_server.pairing.exceptions import (
    InvalidTokenError,
    PairingError,
    ReplayAttackError,
    TokenConsumedError,
    TokenGenerationError,
    TokenRevokedError,
)
from management_server.pairing.manager import PairingManager
from management_server.pairing.schemas import (
    ErrorResponse,
    PairingConsumeRequest,
    PairingConsumeResponse,
    PairingTokenCreateRequest,
    PairingTokenResponse,
    PairingValidateRequest,
    PairingValidateResponse,
)

router = APIRouter(prefix="/api/v1", tags=["pairing"])


async def _get_pairing_manager(request: Request) -> PairingManager:
    """Dependency: get the pairing manager from app state.

    Authentication boundary — wrap with auth middleware later.
    """
    mgr: PairingManager | None = getattr(request.app.state, "pairing_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Pairing manager not initialized")
    return mgr


@router.post(
    "/pairing",
    response_model=PairingTokenResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Generate a pairing token",
)
async def create_pairing_token(
    body: PairingTokenCreateRequest,
    manager: PairingManager = Depends(_get_pairing_manager),  # noqa: B008
) -> PairingTokenResponse:
    """Generate a new secure pairing token.

    Returns the plaintext token exactly once. Only the SHA-256 hash is stored.
    """
    try:
        return await manager.create_token(body)
    except TokenGenerationError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/pairing/validate",
    response_model=PairingValidateResponse,
    summary="Validate a pairing token",
)
async def validate_pairing_token(
    body: PairingValidateRequest,
    manager: PairingManager = Depends(_get_pairing_manager),  # noqa: B008
) -> PairingValidateResponse:
    """Validate a pairing token without consuming it."""
    return await manager.validate_token(body)


@router.post(
    "/pairing/consume",
    response_model=PairingConsumeResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    summary="Consume a pairing token",
)
async def consume_pairing_token(
    body: PairingConsumeRequest,
    manager: PairingManager = Depends(_get_pairing_manager),  # noqa: B008
) -> PairingConsumeResponse:
    """Consume a pairing token and complete pairing.

    Validates the token, marks it consumed, and initiates machine registration.
    """
    try:
        return await manager.consume_token(body)
    except (
        InvalidTokenError,
        TokenConsumedError,
        TokenRevokedError,
        ReplayAttackError,
        PairingError,
    ) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/pairing/{token_id}",
    responses={404: {"model": ErrorResponse}},
    summary="Get pairing token info",
)
async def get_pairing_token(
    token_id: str,
    manager: PairingManager = Depends(_get_pairing_manager),  # noqa: B008
) -> dict[str, object]:
    """Get public info about a pairing token.

    Does not expose the token hash or plaintext value.
    """
    from management_server.pairing.exceptions import PairingRepositoryError

    try:
        return await manager.get_token_info(token_id)  # type: ignore[no-any-return]
    except PairingRepositoryError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
