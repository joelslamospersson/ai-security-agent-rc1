"""
Immutable configuration settings objects.

Every subsystem accesses configuration exclusively through this module.

Usage:
    from security_agent.config.settings import load_settings

    settings = load_settings()
    backend = settings.database.backend
    debug = settings.general.debug
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config.loader import load_config

# ============================================================
# General
# ============================================================


@dataclass(frozen=True)
class GeneralSettings:
    debug: bool = False
    log_level: str = "INFO"
    hostname: str = ""
    profile: str = "default"


# ============================================================
# Logging
# ============================================================


@dataclass(frozen=True)
class LoggingSettings:
    format: str = "console"
    file: str | None = None
    rotation: str = "1 day"
    retention: str = "30 days"


# ============================================================
# Database
# ============================================================


@dataclass(frozen=True)
class SQLiteSettings:
    path: str = "/var/lib/ai-security-agent/data/agent.db"
    wal_mode: bool = True
    busy_timeout: int = 5000
    cache_size: int = -64000


@dataclass(frozen=True)
class PostgresSettings:
    host: str = "localhost"
    port: int = 5432
    database: str = "ai_security"
    user: str = "ai_security"
    password: str = ""
    max_connections: int = 10
    connect_timeout: int = 10


@dataclass(frozen=True)
class MySQLSettings:
    host: str = "localhost"
    port: int = 3306
    database: str = "ai_security"
    user: str = "ai_security"
    password: str = ""
    max_connections: int = 10
    connect_timeout: int = 10


@dataclass(frozen=True)
class DatabaseSettings:
    backend: str = "sqlite"
    sqlite: SQLiteSettings = field(default_factory=SQLiteSettings)
    postgres: PostgresSettings = field(default_factory=PostgresSettings)
    mysql: MySQLSettings = field(default_factory=MySQLSettings)


# ============================================================
# Discord
# ============================================================


@dataclass(frozen=True)
class DiscordChannels:
    info: str | None = None
    warning: str | None = None
    critical: str | None = None
    security: str | None = None
    system: str | None = None
    bans: str | None = None


@dataclass(frozen=True)
class DiscordSettings:
    enabled: bool = False
    webhook: str | None = None
    bot_token: str | None = None
    guild_id: str | int | None = None
    channels: DiscordChannels = field(default_factory=DiscordChannels)


# ============================================================
# Security
# ============================================================


@dataclass(frozen=True)
class ThresholdSettings:
    ssh_brute_force_count: int = 10
    ssh_brute_force_window: int = 300
    port_scan_count: int = 50
    port_scan_window: int = 60
    http_flood_count: int = 1000
    http_flood_window: int = 60
    auth_failure_count: int = 5
    auth_failure_window: int = 300


@dataclass(frozen=True)
class ReputationSettings:
    decay_points_per_hour: int = 1
    max_decay_daily: int = 24
    initial_score: int = 0
    max_score: int = 100
    min_score: int = -100


@dataclass(frozen=True)
class BanPolicySettings:
    enabled: bool = True
    private_ip_exemption: bool = True
    escalation_enabled: bool = True
    durations: tuple[int, ...] = (0, 1800, 3600, 10800, 86400, 172800, 604800, 0)


@dataclass(frozen=True)
class SecuritySettings:
    learning_mode: bool = False
    learning_duration_hours: int = 48
    trusted_networks: tuple[str, ...] = ()
    whitelist: tuple[str, ...] = ()
    blacklist: tuple[str, ...] = ()
    thresholds: ThresholdSettings = field(default_factory=ThresholdSettings)
    reputation: ReputationSettings = field(default_factory=ReputationSettings)
    ban_policy: BanPolicySettings = field(default_factory=BanPolicySettings)


# ============================================================
# Firewall
# ============================================================


@dataclass(frozen=True)
class FirewallSettings:
    backend: str = "nftables"
    enable_ipv6: bool = True
    ipset_threshold: int = 100
    fail2ban_jail: str = "ai-security-agent"
    cleanup_interval: int = 60


# ============================================================
# Monitoring
# ============================================================


@dataclass(frozen=True)
class JournaldSettings:
    enabled: bool = True
    units: tuple[str, ...] = (
        "ssh.service",
        "sshd.service",
        "docker.service",
        "containerd.service",
    )
    priority: str = "info"


@dataclass(frozen=True)
class LogFilePaths:
    auth: tuple[str, ...] = ("/var/log/auth.log", "/var/log/secure")
    syslog: tuple[str, ...] = ("/var/log/syslog", "/var/log/messages")
    kernel: tuple[str, ...] = ("/var/log/kern.log",)
    nginx: tuple[str, ...] = ("/var/log/nginx/access.log", "/var/log/nginx/error.log")
    apache: tuple[str, ...] = (
        "/var/log/apache2/access.log",
        "/var/log/apache2/error.log",
    )
    firewall: tuple[str, ...] = ("/var/log/firewalld", "/var/log/iptables.log")
    docker: tuple[str, ...] = ("/var/log/docker.log",)
    audit: tuple[str, ...] = ("/var/log/audit/audit.log",)


@dataclass(frozen=True)
class LogFileSettings:
    enabled: bool = True
    paths: LogFilePaths = field(default_factory=LogFilePaths)
    exclude_patterns: tuple[str, ...] = ("*.gz", "*.old", "*.bak")
    max_file_size_mb: int = 100


@dataclass(frozen=True)
class DockerSettings:
    enabled: bool = False
    socket_path: str = "/var/run/docker.sock"


@dataclass(frozen=True)
class AuditdSettings:
    enabled: bool = True
    log_path: str = "/var/log/audit/audit.log"


@dataclass(frozen=True)
class MonitoringSettings:
    journald: JournaldSettings = field(default_factory=JournaldSettings)
    log_files: LogFileSettings = field(default_factory=LogFileSettings)
    docker: DockerSettings = field(default_factory=DockerSettings)
    auditd: AuditdSettings = field(default_factory=AuditdSettings)


# ============================================================
# Performance
# ============================================================


@dataclass(frozen=True)
class QueueSizeSettings:
    event_bus: int = 10000
    db_writer: int = 5000
    alert_queue: int = 1000


@dataclass(frozen=True)
class PerformanceSettings:
    memory_limit_mb: int = 200
    cpu_limit_percent: int = 50
    queue_sizes: QueueSizeSettings = field(default_factory=QueueSizeSettings)


# ============================================================
# Developer
# ============================================================


@dataclass(frozen=True)
class DeveloperSettings:
    developer_mode: bool = False
    profiling: bool = False
    replay_mode: bool = False
    replay_path: str | None = None
    replay_rate: int = 0


# ============================================================
# Metrics
# ============================================================


@dataclass(frozen=True)
class MetricsSettings:
    enabled: bool = True
    collection_interval: int = 15


# ============================================================
# Profiles & Rule Packs
# ============================================================


@dataclass(frozen=True)
class ProfileSettings:
    active: str = "default"
    available: tuple[str, ...] = (
        "default",
        "web_server",
        "reverse_proxy",
        "database",
        "docker_host",
        "game_server",
        "mail_server",
        "development",
        "custom",
    )


@dataclass(frozen=True)
class RulePackSettings:
    active: tuple[str, ...] = ("core",)
    available: tuple[str, ...] = (
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
    )


# ============================================================
# Root Settings
# ============================================================


@dataclass(frozen=True)
class Settings:
    """Root configuration object. All subsystems access config through this."""

    general: GeneralSettings = field(default_factory=GeneralSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    discord: DiscordSettings = field(default_factory=DiscordSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)
    firewall: FirewallSettings = field(default_factory=FirewallSettings)
    monitoring: MonitoringSettings = field(default_factory=MonitoringSettings)
    performance: PerformanceSettings = field(default_factory=PerformanceSettings)
    developer: DeveloperSettings = field(default_factory=DeveloperSettings)
    metrics: MetricsSettings = field(default_factory=MetricsSettings)
    profiles: ProfileSettings = field(default_factory=ProfileSettings)
    rule_packs: RulePackSettings = field(default_factory=RulePackSettings)

    @property
    def is_development(self) -> bool:
        """Convenience: True if developer mode or development profile."""
        return (
            self.developer.developer_mode
            or self.profiles.active == "development"
            or self.general.profile == "development"
        )


# ============================================================
# Builder: converts raw dict → frozen Settings
# ============================================================


def _nest(entry: dict[str, Any], *keys: str) -> dict[str, Any]:
    """Get nested dict value or empty dict."""
    current = entry
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, {})
        else:
            return {}
    return current if isinstance(current, dict) else {}


def build_settings(raw: dict[str, Any]) -> Settings:
    """Convert a raw configuration dictionary into a frozen Settings object."""
    return Settings(
        general=GeneralSettings(
            debug=raw.get("general", {}).get("debug", False),
            log_level=raw.get("general", {}).get("log_level", "INFO"),
            hostname=raw.get("general", {}).get("hostname", ""),
            profile=raw.get("general", {}).get("profile", "default"),
        ),
        logging=LoggingSettings(
            format=raw.get("logging", {}).get("format", "console"),
            file=raw.get("logging", {}).get("file"),
            rotation=raw.get("logging", {}).get("rotation", "1 day"),
            retention=raw.get("logging", {}).get("retention", "30 days"),
        ),
        database=DatabaseSettings(
            backend=raw.get("database", {}).get("backend", "sqlite"),
            sqlite=SQLiteSettings(**_nest(raw, "database", "sqlite")),
            postgres=PostgresSettings(**_nest(raw, "database", "postgres")),
            mysql=MySQLSettings(**_nest(raw, "database", "mysql")),
        ),
        discord=DiscordSettings(
            enabled=raw.get("discord", {}).get("enabled", False),
            webhook=raw.get("discord", {}).get("webhook"),
            bot_token=raw.get("discord", {}).get("bot_token"),
            guild_id=raw.get("discord", {}).get("guild_id"),
            channels=DiscordChannels(**_nest(raw, "discord", "channels")),
        ),
        security=SecuritySettings(
            learning_mode=raw.get("security", {}).get("learning_mode", False),
            learning_duration_hours=raw.get("security", {}).get(
                "learning_duration_hours", 48
            ),
            trusted_networks=tuple(raw.get("security", {}).get("trusted_networks", [])),
            whitelist=tuple(raw.get("security", {}).get("whitelist", [])),
            blacklist=tuple(raw.get("security", {}).get("blacklist", [])),
            thresholds=ThresholdSettings(**_nest(raw, "security", "thresholds")),
            reputation=ReputationSettings(**_nest(raw, "security", "reputation")),
            ban_policy=BanPolicySettings(**_nest(raw, "security", "ban_policy")),
        ),
        firewall=FirewallSettings(
            backend=raw.get("firewall", {}).get("backend", "nftables"),
            enable_ipv6=raw.get("firewall", {}).get("enable_ipv6", True),
            ipset_threshold=raw.get("firewall", {}).get("ipset_threshold", 100),
            fail2ban_jail=raw.get("firewall", {}).get(
                "fail2ban_jail", "ai-security-agent"
            ),
            cleanup_interval=raw.get("firewall", {}).get("cleanup_interval", 60),
        ),
        monitoring=MonitoringSettings(
            journald=JournaldSettings(**_nest(raw, "monitoring", "journald")),
            log_files=LogFileSettings(
                enabled=raw.get("monitoring", {})
                .get("log_files", {})
                .get("enabled", True),
                exclude_patterns=tuple(
                    raw.get("monitoring", {})
                    .get("log_files", {})
                    .get("exclude_patterns", ["*.gz", "*.old", "*.bak"])
                ),
                max_file_size_mb=raw.get("monitoring", {})
                .get("log_files", {})
                .get("max_file_size_mb", 100),
            ),
            docker=DockerSettings(**_nest(raw, "monitoring", "docker")),
            auditd=AuditdSettings(**_nest(raw, "monitoring", "auditd")),
        ),
        performance=PerformanceSettings(
            memory_limit_mb=raw.get("performance", {}).get("memory_limit_mb", 200),
            cpu_limit_percent=raw.get("performance", {}).get("cpu_limit_percent", 50),
            queue_sizes=QueueSizeSettings(**_nest(raw, "performance", "queue_sizes")),
        ),
        developer=DeveloperSettings(
            developer_mode=raw.get("developer", {}).get("developer_mode", False),
            profiling=raw.get("developer", {}).get("profiling", False),
            replay_mode=raw.get("developer", {}).get("replay_mode", False),
            replay_path=raw.get("developer", {}).get("replay_path"),
            replay_rate=raw.get("developer", {}).get("replay_rate", 0),
        ),
        metrics=MetricsSettings(
            enabled=raw.get("metrics", {}).get("enabled", True),
            collection_interval=raw.get("metrics", {}).get("collection_interval", 15),
        ),
        profiles=ProfileSettings(
            active=raw.get("profiles", {}).get("active", "default"),
        ),
        rule_packs=RulePackSettings(
            active=tuple(raw.get("rule_packs", {}).get("active", ["core"])),
        ),
    )


_settings_cache: Settings | None = None


def load_settings(config_path: str | Path | None = None) -> Settings:
    """
    Load, validate, and return the application Settings.

    The result is cached — subsequent calls return the same frozen object.
    Call reload() to force re-reading from disk.
    """
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache

    raw_config = load_config(config_path)
    settings = build_settings(raw_config)
    _settings_cache = settings
    return settings


def reload_settings(config_path: str | Path | None = None) -> Settings:
    """
    Force reload configuration from disk.

    Use this when SIGHUP is received or a config change is detected.
    """
    global _settings_cache
    _settings_cache = None
    return load_settings(config_path)
