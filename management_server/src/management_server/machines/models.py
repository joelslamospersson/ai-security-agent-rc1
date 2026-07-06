"""
Machine database models for the Management Server.

Phase 3: only identity and certificate tables.
Registration and heartbeat models are added in later phases.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from management_server.database.base import TimestampedModel


class MachineIdentityModel(TimestampedModel):  # type: ignore[misc]
    """Persistent machine identity record."""

    __tablename__ = "machine_identities"

    machine_uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    environment: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="production",
    )
    public_key_fingerprint: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="",
    )
    certificate_fingerprint: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="",
    )
    agent_version: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CertificateAuthorityModel(TimestampedModel):  # type: ignore[misc]
    """Root CA metadata."""

    __tablename__ = "certificate_authority"

    subject: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    key_type: Mapped[str] = mapped_column(String(50), nullable=False)
    certificate_pem: Mapped[str] = mapped_column(Text, nullable=False)
    public_key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    serial: Mapped[str] = mapped_column(String(64), nullable=False)
    not_before: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    not_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    is_root: Mapped[bool] = mapped_column(Boolean, default=True)
    is_initialized: Mapped[bool] = mapped_column(Boolean, default=False)


class MachineCertificateModel(TimestampedModel):  # type: ignore[misc]
    """Machine certificate storage."""

    __tablename__ = "machine_certificates"

    machine_uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
    )
    serial: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    certificate_pem: Mapped[str] = mapped_column(Text, nullable=False)
    certificate_fingerprint: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    public_key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    public_key_fingerprint: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revocation_reason: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
    )
