"""Secure pairing protocol for the Management Server."""

from management_server.pairing.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    PairingError,
    PairingRepositoryError,
    ReplayAttackError,
    TokenConsumedError,
    TokenGenerationError,
    TokenRevokedError,
)
from management_server.pairing.exceptions import (
    InvalidTransitionError as PairingInvalidTransitionError,
)
from management_server.pairing.generator import PairingTokenGenerator
from management_server.pairing.manager import PairingManager
from management_server.pairing.metrics import PairingMetricsCollector, PairingMetricsSnapshot
from management_server.pairing.models import PairingToken, TokenState, TokenStateMachine
from management_server.pairing.repository import PairingRepository
from management_server.pairing.schemas import (
    PairingConsumeRequest,
    PairingConsumeResponse,
    PairingTokenCreateRequest,
    PairingTokenResponse,
    PairingValidateRequest,
    PairingValidateResponse,
)
from management_server.pairing.service import PairingService
from management_server.pairing.validator import PairingTokenValidator

__all__ = [
    "ExpiredTokenError",
    "InvalidTokenError",
    "PairingConsumeRequest",
    "PairingConsumeResponse",
    "PairingError",
    "PairingInvalidTransitionError",
    "PairingManager",
    "PairingMetricsCollector",
    "PairingMetricsSnapshot",
    "PairingRepository",
    "PairingRepositoryError",
    "PairingService",
    "PairingToken",
    "PairingTokenCreateRequest",
    "PairingTokenGenerator",
    "PairingTokenResponse",
    "PairingTokenValidator",
    "PairingValidateRequest",
    "PairingValidateResponse",
    "ReplayAttackError",
    "TokenConsumedError",
    "TokenGenerationError",
    "TokenRevokedError",
    "TokenState",
    "TokenStateMachine",
]
