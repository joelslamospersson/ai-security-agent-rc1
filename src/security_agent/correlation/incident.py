"""
Incident manager — creates and manages SecurityIncident objects.
"""

from __future__ import annotations

from typing import Any

from security_agent.correlation.models import (
    ActiveChain,
    AttackChain,
    IncidentState,
    SecurityIncident,
)


class IncidentManager:
    """Manages SecurityIncident creation and lifecycle."""

    def __init__(self) -> None:
        self._incidents: dict[str, SecurityIncident] = {}

    def create_incident(
        self,
        chain_def: AttackChain,
        active: ActiveChain,
    ) -> SecurityIncident:
        """Create a SecurityIncident from a completed chain."""
        matched_rules: list[str] = []
        matched_events: list[str] = []
        for sp in active.stage_progress.values():
            matched_rules.extend(sp.matched_rules)
            matched_events.extend(sp.matched_events)

        total_stages = len(chain_def.stages)
        matched_stages = sum(1 for sp in active.stage_progress.values() if sp.matched)
        progress_pct = (
            int((matched_stages / total_stages) * 100) if total_stages > 0 else 0
        )

        incident = SecurityIncident(
            incident_id=active.incident_id,
            attack_chain_id=chain_def.id,
            correlation_id=f"corr-{active.key_value}",
            state=IncidentState.COMPLETED,
            matched_rules=tuple(matched_rules),
            matched_events=tuple(matched_events),
            progress=progress_pct,
            confidence_modifier=active.confidence,
            evidence=f"Attack chain '{chain_def.name}' completed: "
            f"{matched_stages}/{total_stages} stages, "
            f"{len(matched_rules)} rules matched",
        )

        self._incidents[incident.incident_id] = incident
        return incident

    def get_incident(self, incident_id: str) -> SecurityIncident | None:
        return self._incidents.get(incident_id)

    def expire_incidents(self, active_chains: list[Any]) -> list[SecurityIncident]:
        """Convert expired active chains to expired incidents."""
        expired: list[SecurityIncident] = []
        for ac in active_chains:
            incident = SecurityIncident(
                incident_id=ac.incident_id,
                state=IncidentState.EXPIRED,
                evidence="Attack chain expired",
            )
            self._incidents[incident.incident_id] = incident
            expired.append(incident)
        return expired

    @property
    def incident_count(self) -> int:
        return len(self._incidents)

    def clear(self) -> None:
        self._incidents.clear()
