"""
Notification models — immutable data structures for the Notification Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Any
from uuid import uuid4


class NotificationStatus(StrEnum):
    """Status of a notification in its lifecycle."""

    PENDING = auto()
    QUEUED = auto()
    DISPATCHED = auto()
    DELIVERED = auto()
    FAILED = auto()
    SKIPPED = auto()


class DeliveryResultStatus(StrEnum):
    """Result of a delivery attempt."""

    SUCCESS = auto()
    FAILED = auto()
    RETRY = auto()
    RATE_LIMITED = auto()
    SKIPPED = auto()


@dataclass(frozen=True)
class Notification:
    """Immutable notification object ready for delivery.

    Created from a RoutingDecision. Never modified after creation.
    """

    notification_id: str = ""
    routing_decision_id: str = ""
    machine_id: str = ""
    event_type: str = ""
    destination: str = ""
    priority: str = "normal"
    template: str = "detailed"
    payload: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    @classmethod
    def create(
        cls,
        routing_decision_id: str,
        machine_id: str,
        event_type: str,
        destination: str,
        priority: str = "normal",
        template: str = "detailed",
        payload: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Notification:
        return cls(
            notification_id=uuid4().hex[:16],
            routing_decision_id=routing_decision_id,
            machine_id=machine_id,
            event_type=event_type,
            destination=destination,
            priority=priority,
            template=template,
            payload=payload,
            metadata=metadata or {},
            status=NotificationStatus.PENDING,
        )


@dataclass(frozen=True)
class DeliveryResult:
    """Immutable result of a delivery attempt.

    Multiple DeliveryResults may exist per Notification (retries).
    """

    result_id: str = ""
    notification_id: str = ""
    status: DeliveryResultStatus = DeliveryResultStatus.SUCCESS
    adapter: str = "none"
    latency_ms: float = 0.0
    retry_count: int = 0
    error_code: str = ""
    error_message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    @classmethod
    def success(
        cls,
        notification_id: str,
        adapter: str,
        latency_ms: float = 0.0,
    ) -> DeliveryResult:
        return cls(
            result_id=uuid4().hex[:16],
            notification_id=notification_id,
            status=DeliveryResultStatus.SUCCESS,
            adapter=adapter,
            latency_ms=latency_ms,
        )

    @classmethod
    def failure(
        cls,
        notification_id: str,
        adapter: str,
        error_code: str = "",
        error_message: str = "",
        retry_count: int = 0,
    ) -> DeliveryResult:
        return cls(
            result_id=uuid4().hex[:16],
            notification_id=notification_id,
            status=DeliveryResultStatus.FAILED,
            adapter=adapter,
            error_code=error_code,
            error_message=error_message,
            retry_count=retry_count,
        )


@dataclass
class RetryPolicy:
    """Retry policy metadata (not executed)."""

    max_retries: int = 3
    initial_interval_seconds: int = 30
    backoff_multiplier: float = 2.0
    max_interval_seconds: int = 3600


@dataclass
class QueueItem:
    """A notification in a queue."""

    notification: Notification = field(default_factory=Notification)
    priority: str = "normal"
    queued_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    attempts: int = 0
