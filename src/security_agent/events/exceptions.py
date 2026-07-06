"""
Explicit exceptions for the Event Bus and Event Model subsystems.

All exceptions inherit from EventBusError base class.
Never raise generic Exception from event bus code.
"""

from __future__ import annotations


class EventBusError(Exception):
    """Base exception for all Event Bus errors."""


class InvalidEventError(EventBusError):
    """Raised when an invalid event is submitted to the bus."""


class QueueFullError(EventBusError):
    """Raised when a queue is at capacity and cannot accept new events."""


class QueueEmptyError(EventBusError):
    """Raised when attempting to dequeue from an empty queue."""


class SubscriberError(EventBusError):
    """Raised when a subscriber handler fails repeatedly."""


class EventBusShutdownError(EventBusError):
    """Raised when an operation is attempted on a shutting-down Event Bus."""


class EventValidationError(EventBusError):
    """Raised when event data fails validation checks."""


class PriorityQueueError(EventBusError):
    """Raised on invalid priority queue operations."""
