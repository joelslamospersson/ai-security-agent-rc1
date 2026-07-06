"""
Configuration loading system.

Layered loading with precedence (lowest to highest):
    1. Internal defaults (defaults.py)
    2. config.yaml file
    3. AISEC_* environment variables
    4. Command-line arguments (future)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import yaml

from config.defaults import INTERNAL_DEFAULTS
from config.validator import ConfigValidationError, validate_config

_ENV_PREFIX = "AISEC_"


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """
    Load and validate configuration from all layers.

    Returns a validated configuration dictionary.
    Raises ConfigValidationError if validation fails.
    """
    config = _merge_defaults()

    if config_path:
        file_config = _load_yaml_file(config_path)
        config = _deep_merge(config, file_config)

    env_overrides = _load_env_overrides()
    config = _deep_merge(config, env_overrides)

    errors = validate_config(config)
    if errors:
        raise ConfigValidationError(errors)

    return config


def _merge_defaults() -> dict[str, Any]:
    """Return a deep copy of internal defaults."""
    return cast(dict[str, Any], _deep_copy(INTERNAL_DEFAULTS))


def _load_yaml_file(path: str | Path) -> dict[str, Any]:
    """Read and parse a YAML configuration file."""
    path_obj = Path(path)
    if not path_obj.exists():
        return {}

    try:
        with open(path_obj) as f:
            data = yaml.safe_load(f)
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ConfigValidationError(
                [
                    f"'{path}': root must be a mapping (dict). Got: {type(data).__name__}."
                ]
            )
        return data
    except yaml.YAMLError as e:
        raise ConfigValidationError([f"'{path}': malformed YAML: {e}"]) from e
    except OSError as e:
        raise ConfigValidationError([f"'{path}': cannot read: {e}"]) from e


def _get_env_mappings() -> dict[str, list[str]]:
    """Known environment variable to config path mappings."""
    return {
        "AISEC_LOG_LEVEL": ["general", "log_level"],
        "AISEC_LOG_FILE": ["logging", "file"],
        "AISEC_DB_BACKEND": ["database", "backend"],
        "AISEC_DB_PATH": ["database", "sqlite", "path"],
        "AISEC_DB_HOST": ["database", "postgres", "host"],
        "AISEC_DB_PORT": ["database", "postgres", "port"],
        "AISEC_DISCORD_WEBHOOK": ["discord", "webhook"],
        "AISEC_DISCORD_ENABLED": ["discord", "enabled"],
        "AISEC_PROFILE": ["general", "profile"],
        "AISEC_DEBUG": ["general", "debug"],
        "AISEC_HOSTNAME": ["general", "hostname"],
        "AISEC_TRUSTED_NETWORKS": ["security", "trusted_networks"],
        "AISEC_WHITELIST": ["security", "whitelist"],
        "AISEC_LEARNING_MODE": ["security", "learning_mode"],
        "AISEC_FW_BACKEND": ["firewall", "backend"],
        "AISEC_METRICS_ENABLED": ["metrics", "enabled"],
        "AISEC_QUEUE_SIZE": ["performance", "queue_sizes", "event_bus"],
        "AISEC_MEMORY_LIMIT": ["performance", "memory_limit_mb"],
        "AISEC_RULE_PACKS": ["rule_packs", "active"],
    }


def _load_env_overrides() -> dict[str, Any]:
    """
    Load configuration from AISEC_* environment variables.

    Convention: AISEC_<SECTION>_<KEY>

    Examples:
        AISEC_LOG_LEVEL=DEBUG -> {"general": {"log_level": "DEBUG"}}
        AISEC_DB_BACKEND=sqlite -> {"database": {"backend": "sqlite"}}
        AISEC_TRUSTED_NETWORKS=10.0.0.0/8,192.168.0.0/16
            -> {"security": {"trusted_networks": ["10.0.0.0/8", "192.168.0.0/16"]}}
    """
    overrides: dict[str, Any] = {}
    known_mappings = _get_env_mappings()

    for env_key, env_value in os.environ.items():
        if not env_key.startswith(_ENV_PREFIX):
            continue

        # Look up known mapping first
        if env_key in known_mappings:
            path_parts = known_mappings[env_key]
        else:
            # Auto-split: first part is section, rest is key
            path_str = env_key[len(_ENV_PREFIX) :].lower()
            path_parts = path_str.split("_", 1)
            if len(path_parts) == 1:
                path_parts = [path_parts[0], ""]

        # Convert value
        typed_value = _parse_env_value(env_value)

        # Set into nested dict
        target = overrides
        for part in path_parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]
        target[path_parts[-1]] = typed_value

    return overrides


def _parse_env_value(value: str) -> Any:
    """Parse an environment variable string into a typed value."""
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False
    if value.lower() in ("none", "null", ""):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    if "," in value:
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries.

    - Dict values are merged recursively.
    - Non-dict values in overrides replace values in base.
    - Lists in overrides replace lists in base (not appended).
    """
    result = cast(dict[str, Any], _deep_copy(base))
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = _deep_copy(value)
    return result


def _deep_copy(value: Any) -> Any:
    """Deep copy a value (dicts and lists only; others are immutable)."""
    if isinstance(value, dict):
        return {k: _deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return list(value)
    return value
