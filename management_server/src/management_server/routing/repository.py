"""
Routing repository — database CRUD for routing rules, decisions, and profiles.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.routing.models import RoutingDecision, RoutingRule

logger = structlog.get_logger("routing.repository")


class RoutingRepository:
    """Persists routing decisions, rules, and profiles."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_decision(self, decision: RoutingDecision) -> dict[str, Any]:
        """Persist a routing decision."""
        now = datetime.now(tz=UTC)
        await self._session.execute(
            text("""
                INSERT INTO routing_decisions (id, decision_id, machine_id, event_type,
                    destinations, priority, template, rate_limit_profile,
                    retention_policy, matched_rule, metadata_json, created_at)
                VALUES (:id, :did, :mid, :et, :dest, :pri, :tmpl,
                    :rl, :ret, :rule, :meta, :now)
            """),
            {
                "id": str(uuid.uuid4()),
                "did": decision.decision_id,
                "mid": decision.machine_id,
                "et": decision.event_type,
                "dest": json.dumps(decision.destinations),
                "pri": decision.priority.value,
                "tmpl": decision.template.value,
                "rl": decision.rate_limit_profile,
                "ret": decision.retention_policy,
                "rule": decision.matched_rule,
                "meta": json.dumps(decision.metadata),
                "now": now,
            },
        )
        await self._session.commit()
        return {
            "decision_id": decision.decision_id,
            "machine_id": decision.machine_id,
            "event_type": decision.event_type,
        }

    async def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        """Get a routing decision by ID."""
        result = await self._session.execute(
            text("SELECT * FROM routing_decisions WHERE decision_id = :did"),
            {"did": decision_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    async def list_decisions(
        self, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """List routing decisions with pagination."""
        count_result = await self._session.execute(text("SELECT COUNT(*) FROM routing_decisions"))
        total = count_result.scalar() or 0

        result = await self._session.execute(
            text("""
                SELECT * FROM routing_decisions
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset},
        )
        rows = [dict(r._mapping) for r in result.fetchall()]
        return rows, total

    async def save_rule(self, rule: RoutingRule) -> None:
        """Save or update a routing rule."""
        await self._session.execute(
            text("""
                INSERT INTO routing_rules (name, description, event_types,
                    destinations, priority, template, rate_limit_profile,
                    retention_policy, enabled, created_at, updated_at)
                VALUES (:name, :desc, :et, :dest, :pri, :tmpl, :rl, :ret, :en, :now, :now)
                ON CONFLICT (name) DO UPDATE SET
                    event_types = EXCLUDED.event_types,
                    destinations = EXCLUDED.destinations,
                    priority = EXCLUDED.priority,
                    template = EXCLUDED.template,
                    enabled = EXCLUDED.enabled,
                    updated_at = EXCLUDED.updated_at
            """),
            {
                "name": rule.name,
                "desc": rule.description,
                "et": json.dumps(rule.event_types),
                "dest": json.dumps(rule.destinations),
                "pri": rule.priority.value,
                "tmpl": rule.template.value,
                "rl": rule.rate_limit_profile,
                "ret": rule.retention_policy,
                "en": rule.enabled,
                "now": datetime.now(tz=UTC),
            },
        )
        await self._session.commit()

    async def list_rules(self) -> list[dict[str, Any]]:
        """List all routing rules."""
        result = await self._session.execute(text("SELECT * FROM routing_rules ORDER BY name ASC"))
        return [dict(r._mapping) for r in result.fetchall()]

    async def get_decision_count(self) -> int:
        result = await self._session.execute(text("SELECT COUNT(*) FROM routing_decisions"))
        return result.scalar() or 0

    async def get_rule_count(self) -> int:
        result = await self._session.execute(text("SELECT COUNT(*) FROM routing_rules"))
        return result.scalar() or 0
