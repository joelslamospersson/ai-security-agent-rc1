"""
Registration service — orchestrates the registration workflow.

Manages the full lifecycle: request → validation → approval/rejection → certificate issuance.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from management_server.certificates.manager import CertificateManager
from management_server.machines.exceptions import (
    ApprovalError,
    InvalidTransitionError,
    MachineNotFoundError,
    RegistrationError,
)
from management_server.machines.metrics import RegistryMetricsCollector
from management_server.machines.registry import MachineRegistry
from management_server.machines.repository import MachineRepository
from management_server.machines.schemas import (
    RegistrationRequest,
    RegistrationResponse,
)
from management_server.machines.state_machine import MachineState

logger = structlog.get_logger("machines.service")


class RegistrationService:
    """Registration workflow service.

    Coordinates machine registration, approval, and certificate issuance.
    """

    def __init__(
        self,
        registry: MachineRegistry,
        repository: MachineRepository,
        cert_manager: CertificateManager,
        metrics: RegistryMetricsCollector | None = None,
    ) -> None:
        self._registry = registry
        self._repository = repository
        self._cert_manager = cert_manager
        self._metrics = metrics or RegistryMetricsCollector()

    async def create_registration(self, request: RegistrationRequest) -> RegistrationResponse:
        """Process a new registration request from a machine."""
        if not request.machine_uuid:
            raise RegistrationError("machine_uuid is required")
        if not request.public_key_pem:
            raise RegistrationError("public_key_pem is required")

        # Validate the public key
        pk_fingerprint = self._compute_key_fingerprint(request.public_key_pem)

        try:
            record = await self._registry.register(
                machine_uuid=request.machine_uuid,
                hostname=request.hostname,
                operating_system=request.operating_system,
                architecture=request.architecture,
                environment=request.environment,
                agent_version=request.agent_version,
                public_key_fingerprint=pk_fingerprint,
                public_key_pem=request.public_key_pem,
            )
        except Exception as e:
            logger.error(
                "Registration failed",
                machine_uuid=request.machine_uuid,
                error=str(e),
            )
            raise RegistrationError(str(e)) from e

        return RegistrationResponse(
            machine_uuid=request.machine_uuid,
            status=MachineState.PENDING_REGISTRATION,
            message="Registration request created, pending approval",
            created_at=_parse_dt(record.get("created_at")),
        )

    async def approve(
        self,
        machine_uuid: str,
        approved_by: str = "admin",
        reason: str = "",
    ) -> RegistrationResponse:
        """Approve a pending registration and issue a certificate."""
        try:
            record = await self._repository.get_machine(machine_uuid)
        except MachineNotFoundError:
            raise

        current_status = MachineState(record["status"])
        if current_status != MachineState.PENDING_REGISTRATION:
            raise ApprovalError(f"Cannot approve machine in state {current_status.value}")

        # Issue certificate
        public_key_pem = record.get("public_key_pem", "")
        if not public_key_pem:
            raise ApprovalError("No public key on record for machine")

        try:
            cert = await self._cert_manager.issue_certificate(
                machine_uuid=machine_uuid,
                public_key_pem=public_key_pem,
                hostname=record.get("hostname", ""),
            )
        except Exception as e:
            logger.error(
                "Certificate issuance failed during approval",
                machine_uuid=machine_uuid,
                error=str(e),
            )
            raise ApprovalError(f"Certificate issuance failed: {e}") from e

        # Update registry
        updated = await self._registry.approve(
            machine_uuid=machine_uuid,
            approved_by=approved_by,
            reason=reason,
            certificate_fingerprint=cert.certificate_fingerprint,
        )

        logger.info(
            "Machine approved with certificate",
            machine_uuid=machine_uuid,
            cert_serial=cert.serial,
        )

        return RegistrationResponse(
            machine_uuid=machine_uuid,
            status=MachineState.REGISTERED,
            message=f"Machine approved by {approved_by}",
            created_at=_parse_dt(updated.get("approved_at")),
            certificate_pem=cert.certificate_pem,
        )

    async def reject(
        self,
        machine_uuid: str,
        rejected_by: str = "admin",
        reason: str = "",
    ) -> RegistrationResponse:
        """Reject a pending registration."""
        try:
            await self._registry.reject(
                machine_uuid=machine_uuid,
                rejected_by=rejected_by,
                reason=reason,
            )
        except InvalidTransitionError:
            raise

        return RegistrationResponse(
            machine_uuid=machine_uuid,
            status=MachineState.REJECTED,
            message=reason or f"Rejected by {rejected_by}",
        )

    async def expire(self, machine_uuid: str) -> RegistrationResponse:
        """Expire a pending registration."""
        try:
            await self._registry.expire(machine_uuid)
        except InvalidTransitionError:
            raise

        return RegistrationResponse(
            machine_uuid=machine_uuid,
            status=MachineState.EXPIRED,
            message="Registration request expired",
        )

    async def revoke(
        self,
        machine_uuid: str,
        revoked_by: str = "admin",
        reason: str = "",
    ) -> RegistrationResponse:
        """Revoke a machine and its certificate."""
        try:
            await self._registry.revoke(
                machine_uuid=machine_uuid,
                revoked_by=revoked_by,
                reason=reason,
            )
        except InvalidTransitionError:
            raise

        # Also revoke the certificate
        try:
            await self._cert_manager.revoke_certificate(machine_uuid, reason)
        except Exception as e:
            logger.warning(
                "Certificate revocation failed (machine still revoked in registry)",
                machine_uuid=machine_uuid,
                error=str(e),
            )

        return RegistrationResponse(
            machine_uuid=machine_uuid,
            status=MachineState.REVOKED,
            message=reason or f"Revoked by {revoked_by}",
        )

    async def lookup(self, machine_uuid: str) -> dict[str, Any]:
        """Look up a machine by UUID."""
        result: dict[str, Any] = await self._registry.get_machine(machine_uuid)
        return result

    async def list_machines(
        self,
        status: MachineState | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """List machines."""
        result: dict[str, Any] = await self._registry.list_machines(
            status=status, page=page, page_size=page_size
        )
        return result

    async def get_registration_request(self, machine_uuid: str) -> dict[str, Any] | None:
        """Get the raw registration request record."""
        result: dict[str, Any] | None = await self._repository.get_registration_request(
            machine_uuid
        )
        return result

    async def get_metrics(self) -> dict[str, int | float]:
        """Get registration metrics."""
        result: dict[str, int | float] = await self._registry.get_metrics()
        return result

    @staticmethod
    def _compute_key_fingerprint(public_key_pem: str) -> str:
        """Compute SHA-256 fingerprint of a PEM-encoded Ed25519 public key."""
        try:
            key = serialization.load_pem_public_key(public_key_pem.encode())
            if isinstance(key, ed25519.Ed25519PublicKey):
                raw = key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
                digest = hashes.Hash(hashes.SHA256())
                digest.update(raw)
                return digest.finalize().hex()
            # Fallback for RSA/other key types
            from cryptography.hazmat.primitives import serialization as ser

            der = key.public_bytes(
                encoding=ser.Encoding.DER,
                format=ser.PublicFormat.SubjectPublicKeyInfo,
            )
            d = hashes.Hash(hashes.SHA256())
            d.update(der)
            return d.finalize().hex()
        except Exception:
            return ""


def _parse_dt(value: object) -> datetime | None:
    """Parse a datetime value that might be string or datetime object."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            from dateutil import parser as dateutil_parser

            parsed = dateutil_parser.parse(value)
            if isinstance(parsed, datetime):
                return parsed
            return None
        except Exception:
            return None
    return None
