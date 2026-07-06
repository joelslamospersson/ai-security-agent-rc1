"""
Configuration schema definitions.

Defines the expected type, valid values, and constraints for every
configurable field. Used by the validator to produce clear error messages.
"""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

SchemaType = dict[str, Any]


def _valid_log_levels() -> list[str]:
    return ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _valid_profiles() -> list[str]:
    return [
        "default",
        "web_server",
        "reverse_proxy",
        "database",
        "docker_host",
        "game_server",
        "mail_server",
        "development",
        "custom",
    ]


def _valid_firewall_backends() -> list[str]:
    return ["iptables", "nftables", "ipset", "fail2ban"]


def _valid_db_backends() -> list[str]:
    return ["sqlite", "postgres", "mysql"]


def _valid_log_formats() -> list[str]:
    return ["console", "json"]


def _valid_durations() -> list[str]:
    return [
        "1 hour",
        "6 hours",
        "12 hours",
        "1 day",
        "7 days",
        "30 days",
    ]


def _validate_ip(value: str, path: str) -> list[str]:
    """Validate an IP address or CIDR range."""
    errors: list[str] = []
    try:
        if "/" in value:
            ipaddress.ip_network(value, strict=False)
        else:
            ipaddress.ip_address(value)
    except ValueError:
        errors.append(f"Invalid IP/CIDR at {path}: '{value}'")
    return errors


def _validate_port(value: int, path: str) -> list[str]:
    errors: list[str] = []
    if not (1 <= value <= 65535):
        errors.append(f"Invalid port at {path}: {value} (must be 1-65535)")
    return errors


def _validate_file_path(value: str | None, path: str) -> list[str]:
    errors: list[str] = []
    if value is not None:
        p = Path(value)
        # Just validate format, not existence (may not exist yet)
        if not p.parent.exists():
            errors.append(f"Parent directory does not exist at {path}: '{value}'")
    return errors


def _validate_ip_list(value: list[str], path: str) -> list[str]:
    """Validate a list of IP addresses or CIDR ranges."""
    errors: list[str] = []
    for i, entry in enumerate(value):
        ip_errors = _validate_ip(entry, f"{path}[{i}]")
        errors.extend(ip_errors)
    return errors


def _validate_cidr_list(value: list[str], path: str) -> list[str]:
    """Validate a list of CIDR network ranges."""
    errors: list[str] = []
    for i, entry in enumerate(value):
        ip_errors = _validate_ip(entry, f"{path}[{i}]")
        errors.extend(ip_errors)
    return errors


# ============================================================
# Schema definition: maps each config field to validation rules
# ============================================================
# Each entry: (type | [types], optional validators)
# Validators: {"enum": [...], "range": (lo, hi), "regex": "...", "custom": func}

CONFIG_SCHEMA: SchemaType = {
    "general": {
        "type": dict,
        "fields": {
            "debug": {"type": bool},
            "log_level": {"type": str, "enum": _valid_log_levels()},
            "hostname": {"type": str},
            "profile": {"type": str, "enum": _valid_profiles()},
        },
    },
    "logging": {
        "type": dict,
        "fields": {
            "format": {"type": str, "enum": _valid_log_formats()},
            "file": {"type": (str, type(None))},
            "rotation": {"type": str, "enum": _valid_durations()},
            "retention": {"type": str, "enum": _valid_durations()},
        },
    },
    "database": {
        "type": dict,
        "fields": {
            "backend": {"type": str, "enum": _valid_db_backends()},
            "sqlite": {
                "type": dict,
                "fields": {
                    "path": {"type": str},
                    "wal_mode": {"type": bool},
                    "busy_timeout": {"type": int, "range": (0, 60000)},
                    "cache_size": {"type": int, "range": (-1048576, -1)},
                },
            },
            "postgres": {
                "type": dict,
                "fields": {
                    "host": {"type": str},
                    "port": {"type": int, "custom": _validate_port},
                    "database": {"type": str},
                    "user": {"type": str},
                    "password": {"type": str},
                    "max_connections": {"type": int, "range": (1, 100)},
                    "connect_timeout": {"type": int, "range": (1, 60)},
                },
            },
            "mysql": {
                "type": dict,
                "fields": {
                    "host": {"type": str},
                    "port": {"type": int, "custom": _validate_port},
                    "database": {"type": str},
                    "user": {"type": str},
                    "password": {"type": str},
                    "max_connections": {"type": int, "range": (1, 100)},
                    "connect_timeout": {"type": int, "range": (1, 60)},
                },
            },
        },
    },
    "discord": {
        "type": dict,
        "fields": {
            "enabled": {"type": bool},
            "webhook": {"type": (str, type(None))},
            "bot_token": {"type": (str, type(None))},
            "guild_id": {"type": (str, int, type(None))},
            "channels": {
                "type": dict,
                "fields": {
                    "info": {"type": (str, type(None))},
                    "warning": {"type": (str, type(None))},
                    "critical": {"type": (str, type(None))},
                    "security": {"type": (str, type(None))},
                    "system": {"type": (str, type(None))},
                    "bans": {"type": (str, type(None))},
                },
            },
        },
    },
    "security": {
        "type": dict,
        "fields": {
            "learning_mode": {"type": bool},
            "learning_duration_hours": {"type": int, "range": (1, 720)},
            "trusted_networks": {
                "type": list,
                "item_type": str,
                "custom": _validate_cidr_list,
            },
            "whitelist": {"type": list, "item_type": str, "custom": _validate_ip_list},
            "blacklist": {"type": list, "item_type": str, "custom": _validate_ip_list},
            "thresholds": {
                "type": dict,
                "fields": {
                    "ssh_brute_force_count": {"type": int, "range": (1, 10000)},
                    "ssh_brute_force_window": {"type": int, "range": (1, 86400)},
                    "port_scan_count": {"type": int, "range": (1, 100000)},
                    "port_scan_window": {"type": int, "range": (1, 3600)},
                    "http_flood_count": {"type": int, "range": (1, 1000000)},
                    "http_flood_window": {"type": int, "range": (1, 3600)},
                    "auth_failure_count": {"type": int, "range": (1, 1000)},
                    "auth_failure_window": {"type": int, "range": (1, 86400)},
                },
            },
            "reputation": {
                "type": dict,
                "fields": {
                    "decay_points_per_hour": {"type": int, "range": (0, 100)},
                    "max_decay_daily": {"type": int, "range": (0, 1000)},
                    "initial_score": {"type": int, "range": (-100, 100)},
                    "max_score": {"type": int, "range": (1, 100)},
                    "min_score": {"type": int, "range": (-100, -1)},
                },
            },
            "ban_policy": {
                "type": dict,
                "fields": {
                    "enabled": {"type": bool},
                    "private_ip_exemption": {"type": bool},
                    "escalation_enabled": {"type": bool},
                    "durations": {
                        "type": list,
                        "item_type": int,
                        "min_length": 8,
                        "max_length": 8,
                    },
                },
            },
        },
    },
    "firewall": {
        "type": dict,
        "fields": {
            "backend": {"type": str, "enum": _valid_firewall_backends()},
            "enable_ipv6": {"type": bool},
            "ipset_threshold": {"type": int, "range": (1, 10000)},
            "fail2ban_jail": {"type": str},
            "cleanup_interval": {"type": int, "range": (10, 3600)},
        },
    },
    "monitoring": {
        "type": dict,
        "fields": {
            "journald": {
                "type": dict,
                "fields": {
                    "enabled": {"type": bool},
                    "units": {"type": list, "item_type": str},
                    "priority": {
                        "type": str,
                        "enum": [
                            "emerg",
                            "alert",
                            "crit",
                            "err",
                            "warning",
                            "notice",
                            "info",
                            "debug",
                        ],
                    },
                },
            },
            "log_files": {
                "type": dict,
                "fields": {
                    "enabled": {"type": bool},
                    "paths": {"type": dict},
                    "exclude_patterns": {"type": list, "item_type": str},
                    "max_file_size_mb": {"type": int, "range": (1, 10240)},
                },
            },
            "docker": {
                "type": dict,
                "fields": {
                    "enabled": {"type": bool},
                    "socket_path": {"type": str},
                },
            },
            "auditd": {
                "type": dict,
                "fields": {
                    "enabled": {"type": bool},
                    "log_path": {"type": str},
                },
            },
        },
    },
    "performance": {
        "type": dict,
        "fields": {
            "memory_limit_mb": {"type": int, "range": (50, 250)},
            "cpu_limit_percent": {"type": int, "range": (1, 100)},
            "queue_sizes": {
                "type": dict,
                "fields": {
                    "event_bus": {"type": int, "range": (100, 100000)},
                    "db_writer": {"type": int, "range": (100, 50000)},
                    "alert_queue": {"type": int, "range": (10, 10000)},
                },
            },
        },
    },
    "developer": {
        "type": dict,
        "fields": {
            "developer_mode": {"type": bool},
            "profiling": {"type": bool},
            "replay_mode": {"type": bool},
            "replay_path": {"type": (str, type(None))},
            "replay_rate": {"type": int, "range": (0, 100000)},
        },
    },
    "metrics": {
        "type": dict,
        "fields": {
            "enabled": {"type": bool},
            "collection_interval": {"type": int, "range": (1, 3600)},
        },
    },
    "profiles": {
        "type": dict,
        "fields": {
            "active": {"type": str, "enum": _valid_profiles()},
            "available": {"type": list, "item_type": str},
        },
    },
    "rule_packs": {
        "type": dict,
        "fields": {
            "active": {"type": list, "item_type": str},
            "available": {"type": list, "item_type": str},
        },
    },
}
