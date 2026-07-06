"""Firewall state tracking — manages desired vs actual state."""

from __future__ import annotations

from typing import Any


class FirewallState:
    """Tracks desired firewall state for synchronization."""

    def __init__(self) -> None:
        self._desired: dict[str, dict[str, Any]] = {}

    def add_desired(self, entity: str, entity_type: str, **kwargs: Any) -> None:
        self._desired[entity] = {
            "entity": entity,
            "entity_type": entity_type,
            **kwargs,
        }

    def remove_desired(self, entity: str) -> None:
        self._desired.pop(entity, None)

    def is_desired(self, entity: str) -> bool:
        return entity in self._desired

    def get_desired(self) -> list[dict[str, Any]]:
        return list(self._desired.values())

    def desired_count(self) -> int:
        return len(self._desired)

    def compute_sync_actions(
        self,
        desired_ips: set[str],
        actual_ips: set[str],
    ) -> tuple[list[str], list[str]]:
        to_add = list(desired_ips - actual_ips)
        to_remove = list(actual_ips - desired_ips)
        return to_add, to_remove

    def clear(self) -> None:
        self._desired.clear()
