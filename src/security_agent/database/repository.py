"""
Repository layer — isolates SQL from business logic.

Each repository wraps a DatabaseBackend and provides typed methods.
Future PostgreSQL/MySQL support requires only swapping the backend.
"""

from __future__ import annotations

import json
from typing import Any

from security_agent.database.backend import DatabaseBackend


class EventRepository:
    """Events — normalized security events."""

    def __init__(self, db: DatabaseBackend) -> None:
        self._db = db

    async def store(
        self,
        event_id: str,
        timestamp: str,
        source: str,
        source_type: str,
        event_type: int,
        severity: int,
        source_ip: str | None = None,
        raw_message: str = "",
        metadata: dict | None = None,
    ) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO events "
            "(event_id, timestamp, hostname, source, source_type, event_type, "
            "severity, source_ip, raw_message, metadata) "
            "VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                timestamp,
                source,
                source_type,
                event_type,
                severity,
                source_ip,
                raw_message,
                json.dumps(metadata or {}),
            ),
        )

    async def count(self) -> int:
        row = await self._db.fetch_one("SELECT COUNT(*) AS c FROM events")
        return int(row["c"]) if row else 0

    async def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
        )


class RuleMatchRepository:
    """Rule matches from the Rule Engine."""

    def __init__(self, db: DatabaseBackend) -> None:
        self._db = db

    async def store(
        self,
        match_id: str,
        rule_id: str,
        rule_name: str,
        event_id: str,
        confidence: int,
        severity: int,
        threat_score: int,
        evidence: str = "",
    ) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO rule_matches "
            "(match_id, rule_id, rule_name, event_id, confidence, severity, "
            "threat_score, evidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                match_id,
                rule_id,
                rule_name,
                event_id,
                confidence,
                severity,
                threat_score,
                evidence,
            ),
        )

    async def count_by_rule(self, rule_id: str) -> int:
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS c FROM rule_matches WHERE rule_id = ?", (rule_id,)
        )
        return int(row["c"]) if row else 0


class IncidentRepository:
    """Security incidents from the Correlation Engine."""

    def __init__(self, db: DatabaseBackend) -> None:
        self._db = db

    async def store(
        self,
        incident_id: str,
        attack_chain_id: str,
        state: str,
        matched_rules: list[str],
        matched_events: list[str],
        progress: int,
        evidence: str = "",
    ) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO incidents "
            "(incident_id, attack_chain_id, state, matched_rules, "
            "matched_events, progress, evidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                incident_id,
                attack_chain_id,
                state,
                json.dumps(matched_rules),
                json.dumps(matched_events),
                progress,
                evidence,
            ),
        )


class ThreatRepository:
    """Threat assessments from the Threat Engine."""

    def __init__(self, db: DatabaseBackend) -> None:
        self._db = db

    async def store(
        self,
        threat_id: str,
        incident_id: str,
        confidence: int,
        threat_score: int,
        severity: int,
        risk_level: int,
        recommended_action: int,
    ) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO threat_assessments "
            "(threat_id, incident_id, confidence, threat_score, severity, "
            "risk_level, recommended_action) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                threat_id,
                incident_id,
                confidence,
                threat_score,
                severity,
                risk_level,
                recommended_action,
            ),
        )


class ReputationRepository:
    """Reputation records."""

    def __init__(self, db: DatabaseBackend) -> None:
        self._db = db

    async def store(
        self,
        entity_type: str,
        entity_value: str,
        current_score: int,
        confidence: int,
        event_count: int,
        ban_count: int,
        decay_state: str = "active",
    ) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO reputation "
            "(entity_type, entity_value, current_score, confidence, "
            "event_count, ban_count, decay_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                entity_type,
                entity_value,
                current_score,
                confidence,
                event_count,
                ban_count,
                decay_state,
            ),
        )


class BanRepository:
    """Ban history."""

    def __init__(self, db: DatabaseBackend) -> None:
        self._db = db

    async def store(
        self,
        ban_id: str,
        entity: str,
        entity_type: str,
        action: str,
        ban_level: int,
        duration: int,
        reason: str = "",
    ) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO ban_history "
            "(ban_id, entity, entity_type, action, ban_level, duration, reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ban_id, entity, entity_type, action, ban_level, duration, reason),
        )


class FirewallRepository:
    """Firewall operations."""

    def __init__(self, db: DatabaseBackend) -> None:
        self._db = db

    async def store(
        self,
        operation_id: str,
        entity: str,
        entity_type: str,
        operation_type: str,
        duration: int,
        status: str = "pending",
        reason: str = "",
    ) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO firewall_ops "
            "(operation_id, entity, entity_type, operation_type, duration, "
            "status, reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                operation_id,
                entity,
                entity_type,
                operation_type,
                duration,
                status,
                reason,
            ),
        )
