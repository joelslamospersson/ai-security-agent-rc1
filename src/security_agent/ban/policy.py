"""
Ban policies — influence escalation speed and thresholds.

Policies only influence decisions. Never enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass

from security_agent.ban.models import BanPolicy


@dataclass
class PolicyConfig:
    """Configuration for a single ban policy."""

    name: str = ""
    description: str = ""
    min_threat_score: int = 40
    min_confidence: int = 50
    min_reputation: int = -100
    escalation_rate: float = 1.0
    max_level: int = 7
    enable_warnings: bool = True
    enable_temporary_bans: bool = True
    enable_permanent_bans: bool = True


POLICY_DEFAULTS: dict[str, PolicyConfig] = {
    BanPolicy.AGGRESSIVE: PolicyConfig(
        name="aggressive",
        description="Low threshold, fast escalation, permanent on repeat",
        min_threat_score=20,
        min_confidence=40,
        escalation_rate=2.0,
        max_level=7,
    ),
    BanPolicy.BALANCED: PolicyConfig(
        name="balanced",
        description="Moderate thresholds, standard escalation",
        min_threat_score=40,
        min_confidence=60,
        escalation_rate=1.0,
        max_level=7,
    ),
    BanPolicy.CONSERVATIVE: PolicyConfig(
        name="conservative",
        description="High thresholds, slow escalation, no permanent by default",
        min_threat_score=60,
        min_confidence=80,
        escalation_rate=0.5,
        max_level=6,
        enable_permanent_bans=False,
    ),
    BanPolicy.LEARNING: PolicyConfig(
        name="learning",
        description="Warnings only, no bans during learning",
        min_threat_score=80,
        min_confidence=90,
        escalation_rate=0.0,
        max_level=0,
        enable_temporary_bans=False,
        enable_permanent_bans=False,
    ),
    BanPolicy.CUSTOM: PolicyConfig(
        name="custom",
        description="User-configured policy",
        escalation_rate=1.0,
    ),
}


def get_policy(policy_name: str) -> PolicyConfig:
    """Get a policy configuration by name."""
    return POLICY_DEFAULTS.get(policy_name, POLICY_DEFAULTS[BanPolicy.BALANCED])
