"""
Event Envelope — wraps every event published to the Event Bus.

The Event Bus transports EventEnvelope instances, never raw events.
The envelope carries delivery metadata alongside the event payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, auto

from security_agent.events.models import BaseEvent


class DeliveryStatus(IntEnum):
    """Current delivery status of an envelope."""

    PENDING = auto()
    DELIVERING = auto()
    DELIVERED = auto()
    FAILED = auto()
    DROPPED = auto()


@dataclass(slots=True, frozen=True)
class EventEnvelope:
    """Wrapper for every event transported by the Event Bus.

    The envelope is created by the bus when publish() is called.
    It is never created directly by publishers.

    Fields:
        event:       The wrapped event (immutable dataclass)
        publish_ts:  UTC timestamp when publish() was called
        publisher:   Name of the component that published the event
        queue_name:  Name of the queue this envelope was dispatched to
    """

    event: BaseEvent
    publish_ts: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    publisher: str = ""
    delivery_attempts: int = 0
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    queue_name: str = "default"
