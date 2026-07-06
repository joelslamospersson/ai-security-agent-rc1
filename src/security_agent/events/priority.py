"""
Event priority levels.

Priority controls queue ordering (higher priority events are processed first).
Priority must NEVER bypass security guarantees:

- All events are still validated, logged, and audited regardless of priority.
- Priority only affects the order in which events are dequeued.
- CRITICAL priority exists for system-health events, not to skip security checks.
"""

from __future__ import annotations

from enum import IntEnum


class Priority(IntEnum):
    """Event delivery priority.

    Lower numeric value = higher priority (delivered first).
    """

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


# Default priority for events that don't specify one.
DEFAULT_PRIORITY = Priority.NORMAL
