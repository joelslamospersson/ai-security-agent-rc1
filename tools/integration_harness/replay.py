"""
Replay — records and replays scenarios for deterministic testing.

Recorded scenarios produce identical results on replay.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from integration_harness.models import ScenarioEvent


class ScenarioRecorder:
    """Records all events in a scenario for later replay."""

    def __init__(self, output_dir: str = "artifacts") -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._events: list[ScenarioEvent] = []
        self._start_time: float = 0.0

    def start(self) -> None:
        """Start recording."""
        self._events.clear()
        self._start_time = time.time()

    def record(self, event_type: str, source: str, data: dict[str, Any]) -> None:
        """Record a single event."""
        self._events.append(ScenarioEvent(
            timestamp=time.time() - self._start_time,
            event_type=event_type,
            source=source,
            data=dict(data),
        ))

    def save(self, scenario_name: str) -> Path:
        """Save recorded events to a file."""
        path = self._output_dir / f"{scenario_name}_recording.json"
        data = {
            "scenario": scenario_name,
            "duration": time.time() - self._start_time,
            "events": [
                {"timestamp": e.timestamp, "type": e.event_type,
                 "source": e.source, "data": e.data}
                for e in self._events
            ],
        }
        path.write_text(json.dumps(data, indent=2, default=str))
        return path


class ScenarioPlayer:
    """Plays back a previously recorded scenario."""

    def __init__(self) -> None:
        self._events: list[ScenarioEvent] = []

    def load(self, path: Path) -> list[ScenarioEvent]:
        """Load recorded events from a file."""
        data = json.loads(path.read_text())
        self._events = [
            ScenarioEvent(
                timestamp=e["timestamp"],
                event_type=e["type"],
                source=e["source"],
                data=e["data"],
            )
            for e in data.get("events", [])
        ]
        return self._events
