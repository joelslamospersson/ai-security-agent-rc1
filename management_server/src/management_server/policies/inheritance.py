"""
Policy inheritance — resolves single inheritance chains with circular detection.
"""

from __future__ import annotations

import structlog

from management_server.policies.exceptions import InheritanceError
from management_server.policies.models import FeatureFlags, Policy

logger = structlog.get_logger("policies.inheritance")


class PolicyInheritanceEngine:
    """Resolves policy inheritance chains.

    Supports single inheritance (one parent per policy).
    Detects and rejects circular hierarchies.
    """

    def __init__(self, policies: dict[str, Policy] | None = None) -> None:
        self._policies: dict[str, Policy] = {}
        if policies:
            self._policies.update(policies)

    def register(self, policy: Policy) -> None:
        """Register a policy for inheritance resolution."""
        self._policies[policy.name] = policy

    def register_all(self, policies: list[Policy]) -> None:
        """Register multiple policies."""
        for p in policies:
            self._policies[p.name] = p

    def resolve(self, policy_name: str) -> Policy:
        """Resolve a policy by applying inheritance from its ancestors.

        Returns a fully resolved Policy with all inherited values applied.
        Raises InheritanceError if circular dependency is detected.
        """
        if policy_name not in self._policies:
            raise InheritanceError(f"Policy '{policy_name}' not found")

        # Detect cycles with DFS
        chain = self._build_chain(policy_name)
        resolved = self._merge_chain(chain)
        return resolved

    def _build_chain(self, name: str, visited: set[str] | None = None) -> list[Policy]:
        """Build the inheritance chain from most derived to most base.

        Returns list [derived, ..., root].
        Raises InheritanceError on circular dependency.
        """
        if visited is None:
            visited = set()

        if name in visited:
            raise InheritanceError(f"Circular inheritance detected: '{name}' already in chain")

        if name not in self._policies:
            raise InheritanceError(f"Policy '{name}' not found in inheritance chain")

        policy = self._policies[name]
        visited.add(name)

        if policy.has_parent:
            chain = self._build_chain(policy.parent, visited)
            chain.insert(0, policy)
            return chain

        return [policy]

    def _merge_chain(self, chain: list[Policy]) -> Policy:
        """Merge a chain of policies (most derived first) into one resolved policy.

        The most derived policy's values take priority over ancestors.
        """
        # Start with the most base policy
        base = chain[-1]
        merged = Policy(
            name=chain[0].name,
            description=base.description,
            version=chain[0].version,
            parent=chain[0].parent,
            checksum=base.checksum,
            heartbeat_interval_seconds=base.heartbeat_interval_seconds,
            notification_retention_days=base.notification_retention_days,
            log_retention_days=base.log_retention_days,
            ip_masking_enabled=base.ip_masking_enabled,
            maintenance_mode=base.maintenance_mode,
            allowed_protocol_versions=list(base.allowed_protocol_versions),
            feature_flags=FeatureFlags(
                discord=base.feature_flags.discord,
                geoip=base.feature_flags.geoip,
                docker=base.feature_flags.docker,
                web_dashboard=base.feature_flags.web_dashboard,
                remote_commands=base.feature_flags.remote_commands,
                experimental=base.feature_flags.experimental,
            ),
            raw_yaml=dict(base.raw_yaml),
        )

        # Apply each derived policy's values (most derived first, then up)
        for policy in reversed(chain[:-1]):
            if policy is merged:
                continue
            self._apply_overrides(merged, policy)

        return merged

    @staticmethod
    def _apply_overrides(target: Policy, source: Policy) -> None:
        """Apply values from source onto target (source overrides target)."""
        target.description = source.description or target.description
        target.heartbeat_interval_seconds = source.heartbeat_interval_seconds
        target.notification_retention_days = source.notification_retention_days
        target.log_retention_days = source.log_retention_days
        target.ip_masking_enabled = source.ip_masking_enabled
        target.maintenance_mode = source.maintenance_mode
        if source.allowed_protocol_versions != target.allowed_protocol_versions:
            target.allowed_protocol_versions = list(source.allowed_protocol_versions)

        ff = target.feature_flags
        src_ff = source.feature_flags
        ff.discord = src_ff.discord or ff.discord
        ff.geoip = src_ff.geoip or ff.geoip
        ff.docker = src_ff.docker or ff.docker
        ff.web_dashboard = src_ff.web_dashboard or ff.web_dashboard
        ff.remote_commands = src_ff.remote_commands or ff.remote_commands
        ff.experimental = src_ff.experimental or ff.experimental

    def detect_circular(self, policies: list[Policy] | None = None) -> list[str]:
        """Detect circular inheritance in all registered policies.

        Returns a list of policy names involved in cycles.
        """
        if policies:
            self.register_all(policies)

        circular: list[str] = []
        for name in self._policies:
            try:
                self._build_chain(name)
            except InheritanceError:
                circular.append(name)

        return circular

    @property
    def max_depth(self) -> int:
        """Compute the maximum inheritance depth across all policies."""
        max_d = 0
        for name in self._policies:
            try:
                chain = self._build_chain(name)
                max_d = max(max_d, len(chain))
            except InheritanceError:
                continue
        return max_d

    def get_ancestors(self, policy_name: str) -> list[str]:
        """Get the list of ancestor policy names (most recent first)."""
        try:
            chain = self._build_chain(policy_name)
            return [p.name for p in chain[1:]]  # Exclude the policy itself
        except InheritanceError:
            return []
