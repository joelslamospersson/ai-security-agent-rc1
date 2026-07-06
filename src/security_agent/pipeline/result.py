"""
Processing results returned by pipeline stages.

Every stage returns a ProcessingResult that tells the Pipeline Engine
how to proceed with the event.
"""

from __future__ import annotations

from enum import IntEnum


class ProcessingResult(IntEnum):
    """Result of processing an event through a pipeline stage.

    The Pipeline Engine reacts based on this result:
        CONTINUE:  Proceed to the next stage.
        DROP:      Drop the event silently (no further processing).
        RETRY:     Retry the current stage (up to max_retries).
        STOP:      Stop the pipeline for this event (logged).
        ERROR:     Stop with error (logged, metrics incremented).
    """

    CONTINUE = 0
    DROP = 1
    RETRY = 2
    STOP = 3
    ERROR = 4


# Maximum number of retries before a stage is considered failed.
DEFAULT_MAX_RETRIES = 3

# Base delay in seconds before the first retry.
DEFAULT_RETRY_DELAY = 1.0
