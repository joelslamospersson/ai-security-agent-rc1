"""
Detector capabilities — declare what events a detector can process.

The DetectorManager uses capabilities to route only compatible events
to each detector, avoiding unnecessary analysis calls.
"""

from __future__ import annotations

from dataclasses import dataclass

from security_agent.events import EventCategory, EventType


@dataclass(slots=True, frozen=True)
class DetectorCapabilities:
    """What event types and data this detector requires.

    All fields are optional. Empty/set to None means "no restriction".

    Fields:
        event_categories: EventCategory values this detector can process.
        event_types: Specific EventType values this detector can process.
        required_metadata: Metadata keys that must be present in the event.
        required_fields: Field names in SecurityEvent that must be populated.
        description: Human-readable description of what this detector does.
    """

    event_categories: tuple[EventCategory, ...] = ()
    event_types: tuple[EventType, ...] = ()
    required_metadata: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()
    description: str = ""

    def can_process(self, event_type: EventType, category: EventCategory) -> bool:
        """Check if this detector can process an event."""
        if self.event_types and event_type not in self.event_types:
            return False
        return not (self.event_categories and category not in self.event_categories)
