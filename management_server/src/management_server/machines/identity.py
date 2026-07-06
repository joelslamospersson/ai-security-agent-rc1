"""
Machine identity — immutable representation of a machine's cryptographic identity.

No registration state, no heartbeat data. Only identity metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True, frozen=True)
class MachineIdentity:
    """Immutable machine identity.

    Represents the cryptographic identity of a registered machine.
    No dynamic state (heartbeats, bans, etc.) belongs here.
    """

    machine_uuid: str = ""
    hostname: str = ""
    environment: str = "production"  # production, staging, development
    public_key_fingerprint: str = ""
    certificate_fingerprint: str = ""
    first_seen: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    agent_version: str = ""
