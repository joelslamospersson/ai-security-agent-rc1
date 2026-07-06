"""
Pipeline context for event processing.

Each event flowing through the pipeline has its own PipelineContext.
Context carries correlation IDs, timing, retry state, and cancellation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageTiming:
    """Timing information for a single stage execution."""

    stage_name: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    retry_count: int = 0
    result: str = ""


@dataclass
class PipelineContext:
    """Context for a single event flowing through the pipeline.

    Created by the Pipeline Engine for each incoming event.
    Propagated through all stages. Carries:

    - correlation_id:  Links events across the pipeline and beyond
    - cancelled:       Whether the pipeline should stop processing
    - metadata:        Shared key-value store for cross-stage communication
    - timing:          Accumulated stage timing data for observability
    - retry_state:     Current retry counts per stage
    """

    correlation_id: str = ""
    cancelled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    stage_timings: list[StageTiming] = field(default_factory=list)
    retry_state: dict[str, int] = field(default_factory=dict)
    created_at: float = field(default_factory=time.monotonic)
    current_stage: str = ""

    @property
    def elapsed_ms(self) -> float:
        """Return milliseconds since this context was created."""
        return (time.monotonic() - self.created_at) * 1000

    def cancel(self) -> None:
        """Mark the pipeline as cancelled."""
        self.cancelled = True

    def increment_retry(self, stage_name: str) -> int:
        """Increment retry count for a stage. Returns new count."""
        current = self.retry_state.get(stage_name, 0) + 1
        self.retry_state[stage_name] = current
        return current

    def retry_count_for(self, stage_name: str) -> int:
        """Return current retry count for a stage."""
        return self.retry_state.get(stage_name, 0)

    def record_timing(self, timing: StageTiming) -> None:
        """Record timing for a completed stage execution."""
        self.stage_timings.append(timing)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set a shared metadata value."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a shared metadata value."""
        return self.metadata.get(key, default)
