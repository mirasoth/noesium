"""Sequential event queue for deterministic processing (RFC-1007 Section 10).

The event queue ensures events are processed sequentially to maintain
deterministic execution. Includes deduplication to filter duplicate events.
"""

from __future__ import annotations

import json
import logging
from collections import OrderedDict, deque
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .event_system import AutonomousEvent


logger = logging.getLogger(__name__)


class EventQueue:
    """Sequential event queue with deduplication (RFC-1007 Section 10).

    Events are enqueued as they arrive and processed sequentially.
    This ensures deterministic execution and prevents race conditions.

    Deduplication:
    - Events are hashed based on type, source, and payload
    - Duplicate events within the dedup window are filtered out
    - Configurable window (default: 5 seconds)

    Example:
        queue = EventQueue(dedup_window_seconds=5.0)
        enqueued = await queue.enqueue(event)  # Returns True if enqueued
        event = await queue.process_next()
    """

    def __init__(self, dedup_window_seconds: float = 5.0):
        """Initialize event queue with deduplication.

        Args:
            dedup_window_seconds: Time window for deduplication (default: 5.0)
        """
        self._queue: deque[AutonomousEvent] = deque()
        self._processing = False
        self._dedup_window = dedup_window_seconds
        self._recent_hashes: OrderedDict[str, datetime] = OrderedDict()
        logger.debug(f"EventQueue initialized with dedup_window={dedup_window_seconds}s")

    def _event_hash(self, event: AutonomousEvent) -> str:
        """Generate hash for deduplication based on type, source, and payload.

        Args:
            event: Event to hash

        Returns:
            16-character hash string
        """
        try:
            payload_str = json.dumps(event.payload, sort_keys=True)
        except (TypeError, ValueError):
            payload_str = str(event.payload)

        content = f"{event.type}:{event.source}:{payload_str}"
        return sha256(content.encode()).hexdigest()[:16]

    def _cleanup_old_hashes(self) -> None:
        """Remove hashes older than dedup window."""
        now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(seconds=self._dedup_window)

        # OrderedDict maintains insertion order, so oldest entries are first
        while self._recent_hashes:
            oldest_hash, oldest_time = next(iter(self._recent_hashes.items()))
            if oldest_time < cutoff:
                self._recent_hashes.pop(oldest_hash)
            else:
                break

    async def enqueue(self, event: AutonomousEvent) -> bool:
        """Add event to queue if not a duplicate (RFC-1007).

        Checks for duplicate events within the dedup window and filters them.

        Args:
            event: Event to enqueue

        Returns:
            True if event was enqueued, False if filtered as duplicate
        """
        # Cleanup old hashes
        self._cleanup_old_hashes()

        # Check for duplicate
        event_hash = self._event_hash(event)
        if event_hash in self._recent_hashes:
            logger.debug(f"Duplicate event filtered: {event.id[:8]} ({event.type})")
            return False

        # Record hash and enqueue
        self._recent_hashes[event_hash] = datetime.now(tz=timezone.utc)
        self._queue.append(event)
        logger.debug(f"Enqueued event {event.id[:8]} (queue size: {len(self._queue)})")
        return True

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

    @property
    def dedup_cache_size(self) -> int:
        """Get number of hashes in dedup cache.

        Returns:
            Number of recent event hashes
        """
        return len(self._recent_hashes)

    def clear(self) -> None:
        """Clear all pending events and dedup cache."""
        self._queue.clear()
        self._recent_hashes.clear()
        logger.debug("EventQueue cleared")
