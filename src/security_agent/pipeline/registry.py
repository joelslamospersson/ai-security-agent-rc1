"""
Stage registry for the Pipeline Engine.

Responsible for registering, ordering, enabling/disabling stages,
and validating stage dependencies.
"""

from __future__ import annotations

from security_agent.pipeline.exceptions import (
    StageNotFoundError,
    StageRegistrationError,
)
from security_agent.pipeline.stage import PipelineStage


class StageRegistry:
    """Registry of pipeline stages.

    Stages are registered in order and processed sequentially.
    The Pipeline Engine reads the stage order from the registry
    and never hardcodes stage ordering.

    Supports:
    - Registering stages (append)
    - Registering stages at specific positions (insert)
    - Enabling/disabling stages
    - Querying enabled stages in order
    - Validating no duplicate registrations
    """

    def __init__(self) -> None:
        self._stages: dict[str, PipelineStage] = {}
        self._order: list[str] = []
        self._enabled: dict[str, bool] = {}

    def register(
        self,
        stage: PipelineStage,
        after: str | None = None,
        before: str | None = None,
    ) -> None:
        """Register a stage.

        Args:
            stage: The stage instance to register.
            after: Name of stage to insert after (optional).
            before: Name of stage to insert before (optional).

        Raises StageRegistrationError if:
        - A stage with the same name is already registered.
        - Both after and before are specified.
        - The referenced stage for after/before does not exist.
        """
        if stage.name in self._stages:
            raise StageRegistrationError(f"Stage '{stage.name}' is already registered")

        if after and before:
            raise StageRegistrationError("Cannot specify both after and before")

        self._stages[stage.name] = stage
        self._enabled[stage.name] = True

        if after:
            if after not in self._stages:
                self._stages.pop(stage.name)
                self._enabled.pop(stage.name)
                raise StageRegistrationError(
                    f"Cannot insert after '{after}': stage not found"
                )
            idx = self._order.index(after)
            self._order.insert(idx + 1, stage.name)
        elif before:
            if before not in self._stages:
                self._stages.pop(stage.name)
                self._enabled.pop(stage.name)
                raise StageRegistrationError(
                    f"Cannot insert before '{before}': stage not found"
                )
            idx = self._order.index(before)
            self._order.insert(idx, stage.name)
        else:
            self._order.append(stage.name)

    def unregister(self, name: str) -> None:
        """Remove a stage from the registry."""
        if name not in self._stages:
            raise StageNotFoundError(f"Stage '{name}' not found")
        del self._stages[name]
        self._enabled.pop(name, None)
        if name in self._order:
            self._order.remove(name)

    def enable(self, name: str) -> None:
        """Enable a previously disabled stage."""
        if name not in self._stages:
            raise StageNotFoundError(f"Stage '{name}' not found")
        self._enabled[name] = True

    def disable(self, name: str) -> None:
        """Disable a stage (skip during processing)."""
        if name not in self._stages:
            raise StageNotFoundError(f"Stage '{name}' not found")
        self._enabled[name] = False

    def is_enabled(self, name: str) -> bool:
        """Check if a stage is enabled."""
        return self._enabled.get(name, False)

    def get_stage(self, name: str) -> PipelineStage:
        """Get a registered stage by name."""
        if name not in self._stages:
            raise StageNotFoundError(f"Stage '{name}' not found")
        return self._stages[name]

    def get_enabled_stages(self) -> list[PipelineStage]:
        """Return all enabled stages in registration order."""
        return [
            self._stages[name] for name in self._order if self._enabled.get(name, False)
        ]

    def get_all_stages(self) -> list[PipelineStage]:
        """Return all registered stages in registration order."""
        return [self._stages[name] for name in self._order]

    @property
    def stage_names(self) -> list[str]:
        """Return names of all registered stages in order."""
        return list(self._order)

    @property
    def enabled_count(self) -> int:
        """Return number of enabled stages."""
        return sum(1 for v in self._enabled.values() if v)

    @property
    def total_count(self) -> int:
        """Return total number of registered stages."""
        return len(self._stages)

    def clear(self) -> None:
        """Remove all stages from the registry."""
        self._stages.clear()
        self._order.clear()
        self._enabled.clear()
