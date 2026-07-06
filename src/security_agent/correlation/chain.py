"""
Chain tracker — manages active attack chain state.
"""

from __future__ import annotations

import time

from security_agent.correlation.models import (
    ActiveChain,
    AttackChain,
    StageProgress,
    StageType,
)


class ChainTracker:
    """Tracks active attack chain instances."""

    def __init__(self) -> None:
        self._chains: dict[tuple[str, str], ActiveChain] = {}

    def start_chain(self, chain: AttackChain, key_value: str) -> ActiveChain:
        now = time.time()
        active = ActiveChain(
            chain_id=chain.id,
            correlation_key=chain.correlation_key.value,
            key_value=key_value,
            created_at=now,
            updated_at=now,
            last_match_at=now,
            stage_progress={
                s.stage_id: StageProgress(stage_id=s.stage_id) for s in chain.stages
            },
            current_stage_index=0,
            confidence=chain.confidence_modifier,
        )
        self._chains[(chain.id, key_value)] = active
        return active

    def get_chain(self, chain_id: str, key_value: str) -> ActiveChain | None:
        return self._chains.get((chain_id, key_value))

    def advance(
        self,
        chain_def: AttackChain,
        active: ActiveChain,
        rule_id: str,
        event_id: str,
    ) -> bool:
        now = time.time()
        active.last_match_at = now
        active.updated_at = now

        for idx, stage in enumerate(chain_def.stages):
            if rule_id not in stage.rule_ids:
                continue
            progress = active.stage_progress[stage.stage_id]

            if stage.stage_type == StageType.ORDERED:
                if idx != active.current_stage_index:
                    continue
                progress.matched = True
                progress.matched_at = now
                progress.matched_rules.append(rule_id)
                progress.matched_events.append(event_id)
                active.current_stage_index = idx + 1
                active.confidence += stage.confidence_modifier
                return bool(active.current_stage_index >= len(chain_def.stages))

            if stage.stage_type in (StageType.OPTIONAL, StageType.UNORDERED):
                progress.matched = True
                progress.matched_at = now
                progress.matched_rules.append(rule_id)
                progress.matched_events.append(event_id)
                active.confidence += stage.confidence_modifier
                return self._all_required_matched(chain_def, active)

            if stage.stage_type == StageType.BRANCH:
                progress.matched = True
                progress.matched_at = now
                progress.matched_rules.append(rule_id)
                progress.matched_events.append(event_id)
                active.confidence += stage.confidence_modifier
                return True

        return False

    def _all_required_matched(
        self, chain_def: AttackChain, active: ActiveChain
    ) -> bool:
        for stage in chain_def.stages:
            if stage.stage_type == StageType.OPTIONAL:
                continue
            sp = active.stage_progress.get(stage.stage_id)
            if sp is None or not sp.matched:
                return False
        return True

    def remove(self, chain_id: str, key_value: str) -> None:
        self._chains.pop((chain_id, key_value), None)

    async def expire_old(self, chain_defs: dict[str, AttackChain]) -> list[ActiveChain]:
        now = time.time()
        expired: list[ActiveChain] = []
        to_remove: list[tuple[str, str]] = []

        for key, active in self._chains.items():
            chain_def = chain_defs.get(key[0])
            if chain_def is None:
                continue
            if active.is_expired(chain_def.timeout, now):
                active.expired = True
                expired.append(active)
                to_remove.append(key)

        for key in to_remove:
            del self._chains[key]

        return expired

    @property
    def active_count(self) -> int:
        return len(self._chains)

    def clear(self) -> None:
        self._chains.clear()
