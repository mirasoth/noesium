"""Sequential event queue for deterministic processing (RFC-1007 Section 10).

The event queue ensures events are processed sequentially to maintain
deterministic execution.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .event_system import AutonomousEvent


logger = logging.getLogger(__name__)


class EventQueue:
    """Sequential event queue for deterministic processing (RFC-1007 Section 10).

    Events are enqueued as they arrive and processed sequentially.
    This ensures deterministic execution and prevents race conditions.

    Example:
        queue = EventQueue()
        await queue.enqueue(event)
        event = await queue.process_next()
    """

    def __init__(self):
        """Initialize event queue."""
        self._queue: deque[AutonomousEvent] = deque()
        self._processing = False
        logger.debug("EventQueue initialized")

    async def enqueue(self, event: AutonomousEvent) -> None:
        """Add event to queue.

        Args:
            event: Event to enqueue
        """
        self._queue.append(event)
        logger.debug(f"Enqueued event {event.id[:8]} (queue size: {len(self._queue)})")

    async def process_next(self) -> AutonomousEvent | None:
        """Get next event for processing.

        Returns:
            Next event or None if queue is empty
        """
        if not self._queue:
            return None

        event = self._queue.popleft()
        logger.debug(f"Processing event {event.id[:8]} (remaining: {len(self._queue)})")
        return event

    @property
    def is_empty(self) -> bool:
        """Check if queue is empty.

        Returns:
            True if queue has no pending events
        """
        return len(self._queue) == 0

    @property
    def size(self) -> int:
        """Get current queue size.

        Returns:
            Number of pending events
        """
        return len(self._queue)

    def clear(self) -> None:
        """Clear all pending events."""
        self._queue.clear()
        logger.debug("EventQueue cleared")
