"""Configuration system for AI Security Agent.

All application configuration is accessed through this module.

Usage:
    from security_agent.config.settings import load_settings

    settings = load_settings("/etc/ai-security-agent/config.yaml")
    backend = settings.database.backend
"""

from security_agent.config.settings import (
    Settings,
    build_settings,
    load_settings,
    reload_settings,
)

__all__ = [
    "Settings",
    "build_settings",
    "load_settings",
    "reload_settings",
]
