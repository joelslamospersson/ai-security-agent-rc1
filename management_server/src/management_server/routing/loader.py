"""
Routing YAML loader — loads routing rules and profiles from YAML files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml

from management_server.routing.exceptions import RoutingLoadError
from management_server.routing.models import (
    Priority,
    RoutingProfile,
    RoutingRule,
    Template,
)

logger = structlog.get_logger("routing.loader")

ROUTING_DIR = "config/routing"


class RoutingLoader:
    """Loads routing rules from YAML files on disk."""

    def __init__(self, base_dir: str | None = None) -> None:
        self._base_dir = Path(base_dir or ROUTING_DIR)

    def load_all(self) -> tuple[list[RoutingRule], list[RoutingProfile]]:
        """Load all routing YAML files from the routing directory."""
        rules: list[RoutingRule] = []
        profiles: list[RoutingProfile] = []

        if not self._base_dir.exists():
            logger.warning("Routing directory not found", path=str(self._base_dir))
            return rules, profiles

        for path in sorted(self._base_dir.glob("*.yaml")):
            try:
                file_rules, file_profiles = self._load_file(path)
                rules.extend(file_rules)
                profiles.extend(file_profiles)
            except RoutingLoadError as e:
                logger.error("Failed to load routing file", path=str(path), error=str(e))

        return rules, profiles

    def _load_file(self, path: Path) -> tuple[list[RoutingRule], list[RoutingProfile]]:
        """Load a single routing YAML file."""
        if not path.exists():
            raise RoutingLoadError(f"File not found: {path}")

        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise RoutingLoadError(f"YAML parse error: {e}") from e

        if not isinstance(data, dict):
            raise RoutingLoadError("YAML root must be a mapping")

        rules = self._parse_rules(data.get("rules", []))
        profiles = self._parse_profiles(data.get("profiles", []))
        return rules, profiles

    def _parse_rules(self, rule_list: list[dict[str, Any]]) -> list[RoutingRule]:
        rules: list[RoutingRule] = []
        for item in rule_list:
            destinations = item.get("destinations", ["console"])
            rules.append(
                RoutingRule(
                    name=str(item.get("name", "")),
                    description=str(item.get("description", "")),
                    event_types=list(item.get("event_types", ["*"])),
                    match_policy=str(item.get("match_policy", "")),
                    match_machine_state=str(item.get("match_machine_state", "")),
                    match_severity=str(item.get("match_severity", "")),
                    match_feature_flags=item.get("match_feature_flags", {}),
                    match_capabilities=list(item.get("match_capabilities", [])),
                    match_environment=str(item.get("match_environment", "")),
                    destinations=destinations,
                    priority=Priority.from_str(item.get("priority", "normal")),
                    template=Template(str(item.get("template", "detailed")).lower()),
                    rate_limit_profile=str(item.get("rate_limit_profile", "normal")),
                    retention_policy=str(item.get("retention_policy", "standard")),
                    enabled=bool(item.get("enabled", True)),
                )
            )
        return rules

    def _parse_profiles(self, profile_list: list[dict[str, Any]]) -> list[RoutingProfile]:
        profiles: list[RoutingProfile] = []
        for item in profile_list:
            from management_server.routing.models import RateLimitProfile

            rl = item.get("rate_limits", {})
            profiles.append(
                RoutingProfile(
                    name=str(item.get("name", "")),
                    rate_limits=RateLimitProfile(
                        critical=str(rl.get("critical", "unlimited")),
                        high=str(rl.get("high", "30/min")),
                        normal=str(rl.get("normal", "10/min")),
                        low=str(rl.get("low", "1/min")),
                        bulk=str(rl.get("bulk", "5/min")),
                    ),
                    default_destinations=list(item.get("default_destinations", ["console"])),
                    default_priority=Priority.from_str(item.get("default_priority", "normal")),
                    default_template=Template(
                        str(item.get("default_template", "detailed")).upper()
                    ),
                )
            )
        return profiles

    def load_yaml_string(self, yaml_string: str) -> tuple[list[RoutingRule], list[RoutingProfile]]:
        """Load routing from a YAML string (for testing/validation)."""
        try:
            data = yaml.safe_load(yaml_string)
        except yaml.YAMLError as e:
            raise RoutingLoadError(f"YAML parse error: {e}") from e
        if not isinstance(data, dict):
            raise RoutingLoadError("YAML root must be a mapping")
        rules = self._parse_rules(data.get("rules", []))
        profiles = self._parse_profiles(data.get("profiles", []))
        return rules, profiles
