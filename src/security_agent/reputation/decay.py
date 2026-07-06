"""
Reputation decay — gradually restores reputation over time.

Permanent offenders remain at their current score.
Decay is deterministic and configurable.
"""

from __future__ import annotations

import time

from security_agent.reputation.models import REPUTATION_MAX, REPUTATION_MIN


def calculate_decay(
    current_score: int,
    last_seen: float,
    decay_rate: int = 1,
    hours_per_point: int = 24,
    is_permanent: bool = False,
) -> int:
    """Calculate decayed reputation score.

    Reputation moves toward 0 at a configurable rate.
    Permanent offenders never decay.

    Args:
        current_score: Current reputation score (-100 to 100).
        last_seen: Unix timestamp of last activity.
        decay_rate: Points to decay per cycle.
        hours_per_point: Hours per decay point.
        is_permanent: If True, score never changes.

    Returns:
        Decayed score.
    """
    if is_permanent:
        return current_score

    seconds_since_update = time.time() - last_seen
    hours_elapsed = seconds_since_update / 3600.0
    points_to_decay = int(hours_elapsed / hours_per_point) * decay_rate

    if points_to_decay <= 0:
        return current_score

    if current_score > 0:
        decayed = current_score - min(points_to_decay, current_score)
    elif current_score < 0:
        decayed = current_score + min(points_to_decay, abs(current_score))
    else:
        return current_score

    return int(max(REPUTATION_MIN, min(REPUTATION_MAX, decayed)))
