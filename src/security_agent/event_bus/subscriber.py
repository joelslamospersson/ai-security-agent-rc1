"""
Subscriber management for the Event Bus.

Each subscription is identified by a unique Subscription token.
Subscribers register interest in specific EventTypes and receive
EventEnvelopes via their handler callback.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from security_agent.events.envelope import EventEnvelope
from security_agent.events.event_types import EventType

# Handler signature: async def handler(envelope: EventEnvelope) -> None
EventHandler = Callable[[EventEnvelope], Awaitable[None]]

# Slow subscriber threshold in seconds
SLOW_SUBSCRIBER_THRESHOLD = 1.0


@dataclass(slots=True, frozen=True)
class Subscription:
    """Token representing a subscriber registration.

    Returned by EventBus.subscribe(). Used to unsubscribe later.
    """

    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.INTERNAL_METRICS
    handler: EventHandler | None = None
    name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.subscription_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Subscription):
            return NotImplemented
        return self.subscription_id == other.subscription_id


class SubscriberRegistry:
    """Manages subscriber registrations.

    Thread-safe for concurrent subscribe/unsubscribe operations.
    """

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[Subscription]] = {}
        self._subscriptions: dict[str, Subscription] = {}

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
        name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Subscription:
        """Register a subscriber for an event type.

        Returns a Subscription token for later unsubscription.
        """
        sub = Subscription(
            event_type=event_type,
            handler=handler,
            name=name or f"subscriber-{len(self._subscriptions) + 1}",
            metadata=metadata or {},
        )

        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        self._subscribers[event_type].append(sub)
        self._subscriptions[sub.subscription_id] = sub
        return sub

    def unsubscribe(self, subscription: Subscription) -> bool:
        """Remove a subscriber registration.

        Returns True if the subscription was found and removed.
        """
        if subscription.subscription_id not in self._subscriptions:
            return False

        subs = self._subscribers.get(subscription.event_type, [])
        self._subscribers[subscription.event_type] = [
            s for s in subs if s.subscription_id != subscription.subscription_id
        ]
        del self._subscriptions[subscription.subscription_id]
        return True

    def get_handlers(self, event_type: EventType) -> list[Subscription]:
        """Return all subscriptions for a given event type."""
        return list(self._subscribers.get(event_type, []))

    @property
    def subscription_count(self) -> int:
        """Return total number of active subscriptions."""
        return len(self._subscriptions)

    def subscriber_count_for(self, event_type: EventType) -> int:
        """Return number of subscribers for a specific event type."""
        return len(self._subscribers.get(event_type, []))

    def get_all_event_types(self) -> list[EventType]:
        """Return all event types that have subscribers."""
        return list(self._subscribers.keys())
