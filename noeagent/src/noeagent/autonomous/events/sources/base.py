"""Base class for event sources (RFC-1007 §7)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bubus import EventBus
    from noeagent.autonomous.event_system import AutonomousEvent

logger = logging.getLogger(__name__)


class BaseEventSource(ABC):
    """Abstract base class for event sources.

    Event sources emit AutonomousEvents to the EventBus.
    They monitor specific domains (timer, filesystem, tools, etc.)
    and convert changes into events.

    All event sources must implement:
    - start(): Begin monitoring and emitting events
    - stop(): Stop monitoring and cleanup resources
    """

    def __init__(self, event_bus: EventBus):
        """Initialize event source.

        Args:
            event_bus: EventBus to emit events to
        """
        self.event_bus = event_bus
        self._running = False
        self.logger = logger

    @abstractmethod
    async def start(self) -> None:
        """Start the event source.

        Begin monitoring and emitting events.
        """

    @abstractmethod
    def stop(self) -> None:
        """Stop the event source.

        Stop monitoring and clean up resources.
        """

    async def _emit_event(self, event: AutonomousEvent) -> None:
        """Emit event to the event bus.

        Args:
            event: Event to emit
        """
        try:
            await self.event_bus.emit(event.type, event)
            self.logger.debug(f"Emitted event: {event.type}")
        except Exception as e:
            self.logger.error(f"Failed to emit event: {e}")

    @property
    def running(self) -> bool:
        """Check if source is running."""
        return self._running
