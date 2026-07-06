"""
Abstract pipeline stage interface.

Every processing stage implements the PipelineStage ABC.
The Pipeline Engine interacts only through this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from security_agent.events.models import BaseEvent
from security_agent.pipeline.context import PipelineContext
from security_agent.pipeline.result import ProcessingResult


class PipelineStage(ABC):
    """Abstract base for all pipeline processing stages.

    Stages are independent processors. They receive events and return
    ProcessingResult values. The Pipeline Engine orchestrates the flow.

    The engine never knows what a stage actually does — it only calls
    initialize(), process(), and shutdown() through this interface.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._initialized = False

    @property
    def name(self) -> str:
        """Unique stage identifier."""
        return self._name

    @property
    def is_initialized(self) -> bool:
        """Whether the stage has been successfully initialized."""
        return self._initialized

    async def initialize(self) -> None:
        """Prepare the stage for processing.

        Called once at pipeline startup, before any events are processed.
        Override to set up resources, connections, or state.
        """
        self._initialized = True

    @abstractmethod
    async def process(
        self,
        event: BaseEvent,
        context: PipelineContext,
    ) -> ProcessingResult:
        """Process a single event.

        Args:
            event: The event to process.
            context: Pipeline context for this event chain.

        Returns:
            ProcessingResult indicating how the engine should proceed.
        """

    async def shutdown(self) -> None:
        """Clean up stage resources.

        Called once during pipeline shutdown.
        Override to release connections, close files, or persist state.
        """
        self._initialized = False
