"""
Policy YAML loader — loads, parses, and deserializes policies from YAML files.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import structlog
import yaml

from management_server.policies.exceptions import PolicyLoadError
from management_server.policies.models import FeatureFlags, Policy

logger = structlog.get_logger("policies.loader")

POLICIES_DIR = "config/policies"


class PolicyLoader:
    """Loads policies from YAML files on disk."""

    def __init__(self, base_dir: str | None = None) -> None:
        self._base_dir = Path(base_dir or POLICIES_DIR)

    def load_all(self) -> list[Policy]:
        """Load all YAML policy files from the policies directory."""
        policies: list[Policy] = []
        if not self._base_dir.exists():
            logger.warning("Policies directory not found", path=str(self._base_dir))
            return policies

        for path in sorted(self._base_dir.glob("*.yaml")):
            try:
                policy = self.load_file(path)
                policies.append(policy)
            except PolicyLoadError as e:
                logger.error("Failed to load policy file", path=str(path), error=str(e))

        return policies

    def load_file(self, path: Path) -> Policy:
        """Load a single policy YAML file."""
        if not path.exists():
            raise PolicyLoadError(path.stem, f"File not found: {path}")

        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise PolicyLoadError(path.stem, f"YAML parse error: {e}") from e

        if not isinstance(data, dict):
            raise PolicyLoadError(path.stem, "YAML root must be a mapping")

        return self._parse_policy(path.stem, data)

    def load_yaml_string(self, name: str, yaml_string: str) -> Policy:
        """Load a policy from a YAML string (for testing/validation)."""
        try:
            data = yaml.safe_load(yaml_string)
        except yaml.YAMLError as e:
            raise PolicyLoadError(name, f"YAML parse error: {e}") from e

        if not isinstance(data, dict):
            raise PolicyLoadError(name, "YAML root must be a mapping")

        return self._parse_policy(name, data)

    def _parse_policy(self, name: str, data: dict[str, Any]) -> Policy:
        """Parse a YAML dict into a Policy object."""
        try:
            raw_yaml = dict(data)
            feature_flags_data = data.get("feature_flags", {})

            # Compute checksum
            yaml_bytes = yaml.dump(data, sort_keys=True).encode()
            checksum = hashlib.sha256(yaml_bytes).hexdigest()

            policy = Policy(
                name=name,
                description=str(data.get("description", "")),
                version=str(data.get("version", "1")),
                parent=str(data.get("parent", "")),
                checksum=checksum,
                heartbeat_interval_seconds=int(data.get("heartbeat_interval_seconds", 30)),
                notification_retention_days=int(data.get("notification_retention_days", 30)),
                log_retention_days=int(data.get("log_retention_days", 90)),
                ip_masking_enabled=bool(data.get("ip_masking_enabled", True)),
                maintenance_mode=bool(data.get("maintenance_mode", False)),
                allowed_protocol_versions=list(data.get("allowed_protocol_versions", ["1.0"])),
                feature_flags=FeatureFlags.from_dict(
                    feature_flags_data if isinstance(feature_flags_data, dict) else {}
                ),
                raw_yaml=raw_yaml,
            )
            return policy
        except Exception as e:
            raise PolicyLoadError(name, str(e)) from e

    @property
    def policy_count(self) -> int:
        if not self._base_dir.exists():
            return 0
        return len(list(self._base_dir.glob("*.yaml")))
