"""
Publisher abstraction for the Event Bus.

Provides a clean interface for components that publish events
without exposing the full EventBus API.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class Publisher:
    """Publisher interface exposed to components.

    Components receive a Publisher instance scoped to their identity.
    The publisher wraps the EventBus and injects the component's
    name as the publisher field on every published event.
    """

    def __init__(
        self,
        publish_fn: Callable[..., Awaitable[None]],
        component_name: str,
    ) -> None:
        self._publish_fn = publish_fn
        self._component_name = component_name

    @property
    def name(self) -> str:
        return self._component_name

    async def publish(self, event_type: Any, event: Any) -> None:
        """Publish an event with this publisher's identity."""
        await self._publish_fn(event_type, event, publisher=self._component_name)

    async def publish_many(self, events: list[tuple[Any, Any]]) -> None:
        """Publish multiple events in batch."""
        for event_type, event in events:
            await self._publish_fn(event_type, event, publisher=self._component_name)
