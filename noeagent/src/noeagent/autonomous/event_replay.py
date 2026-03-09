"""Event replay capability for autonomous mode (RFC-1007).

Provides the ability to replay events from an EventStore for debugging,
recovery, and testing purposes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, AsyncIterator

from .event_system import AutonomousEvent

if TYPE_CHECKING:
    from noesium.core.event.store import EventStore

    from .event_queue import EventQueue


logger = logging.getLogger(__name__)


class EventReplayer:
    """Replay events from EventStore for debugging and recovery (RFC-1007).

    The EventReplayer allows replaying stored events with filtering by:
    - Event type
    - Time range (since/until)
    - Source

    This is useful for:
    - Debugging autonomous agent behavior
    - Recovery after crashes
    - Testing trigger rules with historical events
    - Auditing event history

    Example:
        replayer = EventReplayer(event_store)

        # Replay all events
        async for event in replayer.replay():
            print(f"Event: {event.type}")

        # Replay filesystem events from last hour
        from datetime import datetime, timedelta, timezone
        one_hour_ago = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        async for event in replayer.replay(event_type="filesystem.change", since=one_hour_ago):
            print(f"File event: {event.payload}")
    """

    def __init__(self, event_store: EventStore):
        """Initialize EventReplayer.

        Args:
            event_store: EventStore to replay events from
        """
        self._store = event_store
        logger.debug("EventReplayer initialized")

    async def replay(
        self,
        event_type: str | None = None,
        source: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[AutonomousEvent]:
        """Replay events matching criteria (RFC-1007).

        Iterates through stored events and yields those matching the filters.
        Events are yielded in chronological order.

        Args:
            event_type: Filter by event type (e.g., "timer", "filesystem.change")
            source: Filter by event source (e.g., "watchdog", "github_webhook")
            since: Only events after this time (inclusive)
            until: Only events before this time (inclusive)
            limit: Maximum number of events to replay

        Yields:
            AutonomousEvent objects matching criteria
        """
        count = 0

        try:
            async for envelope in self._store.read_all():
                # Apply filters

                # Filter by event type
                if event_type and envelope.event_type != event_type:
                    continue

                # Filter by time range
                if since and envelope.timestamp < since:
                    continue
                if until and envelope.timestamp > until:
                    continue

                # Extract source from metadata
                event_source = envelope.metadata.get("source", "unknown")

                # Filter by source
                if source and event_source != source:
                    continue

                # Convert envelope to AutonomousEvent
                event = AutonomousEvent(
                    id=envelope.id,
                    type=envelope.event_type,
                    source=event_source,
                    timestamp=envelope.timestamp,
                    payload=envelope.payload,
                )

                yield event

                count += 1
                if limit and count >= limit:
                    logger.debug(f"Replay limit reached: {limit}")
                    break

        except Exception as e:
            logger.error(f"Error during event replay: {e}", exc_info=True)
            raise

        logger.info(f"Replayed {count} events")

    async def replay_to_queue(
        self,
        event_queue: "EventQueue",
        event_type: str | None = None,
        source: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int | None = None,
    ) -> int:
        """Replay events directly into an EventQueue (RFC-1007).

        Convenience method to replay events into a queue for reprocessing.
        Events pass through the queue's deduplication logic.

        Args:
            event_queue: EventQueue to replay into
            event_type: Filter by event type
            source: Filter by event source
            since: Only events after this time
            until: Only events before this time
            limit: Maximum number of events to replay

        Returns:
            Number of events successfully enqueued
        """

        enqueued = 0
        async for event in self.replay(
            event_type=event_type,
            source=source,
            since=since,
            until=until,
            limit=limit,
        ):
            was_enqueued = await event_queue.enqueue(event)
            if was_enqueued:
                enqueued += 1

        logger.info(f"Replayed {enqueued} events to queue")
        return enqueued

    async def count_events(
        self,
        event_type: str | None = None,
        source: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> int:
        """Count events matching criteria without replaying.

        Args:
            event_type: Filter by event type
            source: Filter by event source
            since: Only events after this time
            until: Only events before this time

        Returns:
            Number of matching events
        """
        count = 0
        async for _ in self.replay(
            event_type=event_type,
            source=source,
            since=since,
            until=until,
        ):
            count += 1
        return count

    async def get_event_types(self) -> set[str]:
        """Get all unique event types in the store.

        Returns:
            Set of event type strings
        """
        event_types: set[str] = set()
        async for envelope in self._store.read_all():
            event_types.add(envelope.event_type)
        return event_types

    async def get_event_sources(self) -> set[str]:
        """Get all unique event sources in the store.

        Returns:
            Set of source strings
        """
        sources: set[str] = set()
        async for envelope in self._store.read_all():
            source = envelope.metadata.get("source", "unknown")
            sources.add(source)
        return sources
