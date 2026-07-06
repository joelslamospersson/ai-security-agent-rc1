"""
Virtual time controller — enables fast-forward, pause, and resume.

Allows testing time-dependent features (retention, expiry, decay) without
waiting in real time.
"""

from __future__ import annotations

import time as real_time
from dataclasses import dataclass
from threading import Lock


@dataclass
class VirtualTime:
    """Virtual time state."""

    offset: float = 0.0
    speed: float = 1.0
    paused: bool = False
    paused_at: float = 0.0


class TimeController:
    """Controls virtual time for simulation."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._offset = 0.0
        self._speed = 1.0
        self._paused = False
        self._paused_at = 0.0

    def now(self) -> float:
        """Get the current virtual time."""
        with self._lock:
            if self._paused:
                return self._paused_at
            return real_time.time() * self._speed + self._offset

    def advance(self, seconds: float) -> None:
        """Advance virtual time by a number of seconds."""
        with self._lock:
            self._offset += seconds

    def set_speed(self, speed: float) -> None:
        """Set time speed multiplier."""
        with self._lock:
            now = real_time.time() * self._speed + self._offset
            self._speed = speed
            self._offset = now - real_time.time() * self._speed

    def pause(self) -> None:
        """Pause virtual time."""
        with self._lock:
            if not self._paused:
                self._paused_at = real_time.time() * self._speed + self._offset
                self._paused = True

    def resume(self) -> None:
        """Resume virtual time."""
        with self._lock:
            if self._paused:
                now_real = real_time.time()
                self._offset = self._paused_at - now_real * self._speed
                self._paused = False

    def fast_forward(self, days: float = 0, hours: float = 0, minutes: float = 0) -> None:
        """Fast-forward by a duration."""
        total = days * 86400 + hours * 3600 + minutes * 60
        self.advance(total)

    def get_state(self) -> VirtualTime:
        with self._lock:
            return VirtualTime(
                offset=self._offset,
                speed=self._speed,
                paused=self._paused,
                paused_at=self._paused_at,
            )
