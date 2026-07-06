"""Correlation Engine — correlates RuleMatches into SecurityIncidents."""

from security_agent.correlation.engine import CorrelationEngine
from security_agent.correlation.models import (
    AttackChain,
    ChainStage,
    CorrelationKey,
    IncidentState,
    SecurityIncident,
    StageType,
)

__all__ = [
    "AttackChain",
    "ChainStage",
    "CorrelationEngine",
    "CorrelationKey",
    "IncidentState",
    "SecurityIncident",
    "StageType",
]
