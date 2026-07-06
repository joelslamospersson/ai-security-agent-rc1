"""
Strongly typed event type enums.

EventCategory groups events by subsystem.
EventType identifies the specific kind of event.

Only framework-level event types are defined here.
Detector-specific types are defined by individual detectors.
"""

from __future__ import annotations

from enum import IntEnum, auto


class EventCategory(IntEnum):
    """Top-level category for event classification."""

    LIFECYCLE = auto()
    CONFIGURATION = auto()
    SECURITY = auto()
    MONITORING = auto()
    HEALTH = auto()
    ALERT = auto()
    FIREWALL = auto()
    DATABASE = auto()
    PLUGIN = auto()
    INTERNAL = auto()


class EventType(IntEnum):
    """Specific event type identifier.

    Framework-level types (0-999). Detectors use 1000+ range.
    """

    # Lifecycle (100-199)
    APPLICATION_STARTING = 100
    APPLICATION_STARTED = 101
    APPLICATION_STOPPING = 102
    APPLICATION_STOPPED = 103
    COMPONENT_STARTING = 110
    COMPONENT_STARTED = 111
    COMPONENT_STOPPING = 112
    COMPONENT_STOPPED = 113
    COMPONENT_FAILURE = 114

    # Configuration (200-299)
    CONFIG_LOADING = 200
    CONFIG_LOADED = 201
    CONFIG_CHANGED = 202
    CONFIG_INVALID = 203
    CONFIG_RELOADING = 204
    CONFIG_RELOADED = 205

    # Security (300-399) — framework-level routing only
    SECURITY_EVENT = 300
    SECURITY_DETECTION = 301
    SECURITY_CORRELATED = 302
    SECURITY_THREAT = 303

    # Monitoring (400-499)
    MONITOR_STARTED = 400
    MONITOR_STOPPED = 401
    MONITOR_ERROR = 402
    MONITOR_FILE_ROTATED = 403
    MONITOR_BUFFER_OVERFLOW = 404

    # Health (500-599)
    HEALTH_CHECK = 500
    HEALTH_OK = 501
    HEALTH_WARNING = 502
    HEALTH_CRITICAL = 503
    HEALTH_STALL_DETECTED = 504
    HEALTH_MEMORY_HIGH = 505
    HEALTH_CPU_HIGH = 506

    # Alert (600-699)
    ALERT_TRIGGERED = 600
    ALERT_SENT = 601
    ALERT_FAILED = 602
    ALERT_SUPPRESSED = 603

    # Firewall (700-799)
    FIREWALL_BAN_APPLIED = 700
    FIREWALL_BAN_FAILED = 701
    FIREWALL_BAN_EXPIRED = 702
    FIREWALL_UNBAN = 703
    FIREWALL_RULES_MISSING = 704
    FIREWALL_BACKEND_ERROR = 705

    # Database (800-899)
    DB_CONNECTED = 800
    DB_DISCONNECTED = 801
    DB_ERROR = 802
    DB_MIGRATION_STARTED = 803
    DB_MIGRATION_COMPLETE = 804
    DB_BACKUP_CREATED = 805
    DB_BACKUP_FAILED = 806

    # Plugin (900-999)
    PLUGIN_LOADED = 900
    PLUGIN_UNLOADED = 901
    PLUGIN_ERROR = 902
    PLUGIN_INIT_FAILED = 903

    # Internal (1000-1099)
    INTERNAL_METRICS = 1000
    INTERNAL_QUEUE_BACKPRESSURE = 1001
    INTERNAL_EVENT_DROPPED = 1002
    INTERNAL_SUBSCRIBER_SLOW = 1003
    INTERNAL_TAMPER_DETECTED = 1004

    @classmethod
    def category_for(cls, event_type: EventType) -> EventCategory:
        """Return the category for a given event type."""
        value = event_type.value
        if 100 <= value < 200:
            return EventCategory.LIFECYCLE
        if 200 <= value < 300:
            return EventCategory.CONFIGURATION
        if 300 <= value < 400:
            return EventCategory.SECURITY
        if 400 <= value < 500:
            return EventCategory.MONITORING
        if 500 <= value < 600:
            return EventCategory.HEALTH
        if 600 <= value < 700:
            return EventCategory.ALERT
        if 700 <= value < 800:
            return EventCategory.FIREWALL
        if 800 <= value < 900:
            return EventCategory.DATABASE
        if 900 <= value < 1000:
            return EventCategory.PLUGIN
        return EventCategory.INTERNAL
