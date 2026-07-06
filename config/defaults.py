"""
Internal default configuration values.

These are the lowest-precedence layer. Every configurable value must
have a default defined here.

Overridden by (in order):
    1. config.yaml
    2. AISEC_* environment variables
    3. Command-line arguments (future)
"""

from __future__ import annotations

from typing import Any

INTERNAL_DEFAULTS: dict[str, Any] = {
    "general": {
        "debug": False,
        "log_level": "INFO",
        "hostname": "",  # auto-detected at runtime if empty
        "profile": "default",
    },
    "logging": {
        "format": "console",  # "console" | "json"
        "file": None,  # None = stderr, path = file
        "rotation": "1 day",
        "retention": "30 days",
    },
    "database": {
        "backend": "sqlite",
        "sqlite": {
            "path": "/var/lib/ai-security-agent/data/agent.db",
            "wal_mode": True,
            "busy_timeout": 5000,
            "cache_size": -64000,
        },
        "postgres": {
            "host": "localhost",
            "port": 5432,
            "database": "ai_security",
            "user": "ai_security",
            "password": "",  # must be set via env or config
            "max_connections": 10,
            "connect_timeout": 10,
        },
        "mysql": {
            "host": "localhost",
            "port": 3306,
            "database": "ai_security",
            "user": "ai_security",
            "password": "",
            "max_connections": 10,
            "connect_timeout": 10,
        },
    },
    "discord": {
        "enabled": False,
        "webhook": None,
        "bot_token": None,
        "guild_id": None,
        "channels": {
            "info": None,
            "warning": None,
            "critical": None,
            "security": None,
            "system": None,
            "bans": None,
        },
    },
    "security": {
        "learning_mode": False,
        "learning_duration_hours": 48,
        "trusted_networks": [],
        "whitelist": [],
        "blacklist": [],
        "thresholds": {
            "ssh_brute_force_count": 10,
            "ssh_brute_force_window": 300,
            "port_scan_count": 50,
            "port_scan_window": 60,
            "http_flood_count": 1000,
            "http_flood_window": 60,
            "auth_failure_count": 5,
            "auth_failure_window": 300,
        },
        "reputation": {
            "decay_points_per_hour": 1,
            "max_decay_daily": 24,
            "initial_score": 0,
            "max_score": 100,
            "min_score": -100,
        },
        "ban_policy": {
            "enabled": True,
            "private_ip_exemption": True,
            "escalation_enabled": True,
            "durations": [
                0,  # Level 0: Warning
                1800,  # Level 1: 30 min
                3600,  # Level 2: 1 hr
                10800,  # Level 3: 3 hr
                86400,  # Level 4: 24 hr
                172800,  # Level 5: 2 days
                604800,  # Level 6: 7 days
                0,  # Level 7: Permanent
            ],
        },
    },
    "firewall": {
        "backend": "nftables",
        "enable_ipv6": True,
        "ipset_threshold": 100,
        "fail2ban_jail": "ai-security-agent",
        "cleanup_interval": 60,
    },
    "monitoring": {
        "journald": {
            "enabled": True,
            "units": [
                "ssh.service",
                "sshd.service",
                "docker.service",
                "containerd.service",
            ],
            "priority": "info",
        },
        "log_files": {
            "enabled": True,
            "paths": {
                "auth": ["/var/log/auth.log", "/var/log/secure"],
                "syslog": ["/var/log/syslog", "/var/log/messages"],
                "kernel": ["/var/log/kern.log"],
                "nginx": ["/var/log/nginx/access.log", "/var/log/nginx/error.log"],
                "apache": ["/var/log/apache2/access.log", "/var/log/apache2/error.log"],
                "firewall": ["/var/log/firewalld", "/var/log/iptables.log"],
                "docker": ["/var/log/docker.log"],
                "audit": ["/var/log/audit/audit.log"],
            },
            "exclude_patterns": ["*.gz", "*.old", "*.bak"],
            "max_file_size_mb": 100,
        },
        "docker": {
            "enabled": False,
            "socket_path": "/var/run/docker.sock",
        },
        "auditd": {
            "enabled": True,
            "log_path": "/var/log/audit/audit.log",
        },
    },
    "performance": {
        "memory_limit_mb": 200,
        "cpu_limit_percent": 50,
        "queue_sizes": {
            "event_bus": 10000,
            "db_writer": 5000,
            "alert_queue": 1000,
        },
    },
    "developer": {
        "developer_mode": False,
        "profiling": False,
        "replay_mode": False,
        "replay_path": None,
        "replay_rate": 0,
    },
    "metrics": {
        "enabled": True,
        "collection_interval": 15,
    },
    "profiles": {
        "active": "default",
        "available": [
            "default",
            "web_server",
            "reverse_proxy",
            "database",
            "docker_host",
            "game_server",
            "mail_server",
            "development",
            "custom",
        ],
    },
    "rule_packs": {
        "active": ["core"],
        "available": [
            "core",
            "ssh",
            "nginx",
            "apache",
            "caddy",
            "docker",
            "mysql",
            "postgres",
            "kernel",
            "malware",
            "ddos",
            "game_server",
            "custom",
        ],
    },
}
