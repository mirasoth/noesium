"""Memory change event source (RFC-1007 §7.5)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from noeagent.autonomous.event_system import AutonomousEvent
from noeagent.autonomous.events.sources.base import BaseEventSource

if TYPE_CHECKING:
    from bubus import EventBus

    from noesium.core.memory.provider_manager import ProviderMemoryManager

logger = logging.getLogger(__name__)


class MemoryObserverEventSource(BaseEventSource):
    """Observes memory state changes and emits events.

    Monitors memory system for:
    - New information stored
    - Knowledge graph updates
    - Pattern detection in stored data

    Enables reactive goal creation based on memory changes.

    Example:
        - New research stored → triggers "analyze research" goal
        - Knowledge graph updated → triggers "integrate knowledge" goal
    """

    def __init__(
        self,
        event_bus: EventBus,
        memory_manager: ProviderMemoryManager,
        watch_patterns: list[str] | None = None,
        poll_interval: float = 60.0,
    ):
        """Initialize memory observer.

        Args:
            event_bus: EventBus to emit events to
            memory_manager: Memory manager to observe
            watch_patterns: Key patterns to watch (e.g., ["research:*", "fact:*"])
            poll_interval: Seconds between change checks (default: 60.0)
        """
        super().__init__(event_bus)
        self.memory = memory_manager
        self.watch_patterns = watch_patterns or [
            "research:*",
            "fact:*",
            "knowledge:*",
            "execution:*",
        ]
        self.poll_interval = poll_interval
        self._last_timestamps: dict[str, float] = {}

    async def start(self) -> None:
        """Start monitoring memory changes."""
        self._running = True
        self.logger.info(
            f"MemoryObserverEventSource started, watching {len(self.watch_patterns)} patterns"
        )

    def stop(self) -> None:
        """Stop monitoring memory."""
        self._running = False
        self.logger.info("MemoryObserverEventSource stopped")

    async def check_for_changes(self) -> None:
        """Poll for memory changes.

        Called by autonomous runner periodically to detect changes
        that might warrant goal creation.

        Should be called in a background task with poll_interval.
        """
        if not self._running:
            return

        persistent = self.memory.get_provider("persistent")
        if not persistent:
            return

        for pattern in self.watch_patterns:
            try:
                # List keys matching pattern
                keys = await persistent.list_keys(prefix=pattern.rstrip("*"))

                for key in keys:
                    # Read entry to check timestamp
                    entry = await persistent.read(key)
                    if not entry:
                        continue

                    # Get timestamp
                    timestamp = 0.0
                    if entry.timestamp:
                        timestamp = entry.timestamp.timestamp()

                    # Check if new or updated
                    last_seen = self._last_timestamps.get(key, 0.0)
                    if timestamp > last_seen:
                        self._last_timestamps[key] = timestamp

                        # Emit event for new/updated entry
                        event = AutonomousEvent(
                            type="memory.entry_updated",
                            source="memory_observer",
                            payload={
                                "key": key,
                                "content_type": entry.content_type,
                                "timestamp": timestamp,
                                "is_new": last_seen == 0.0,
                            },
                        )

                        await self._emit_event(event)

            except Exception as e:
                self.logger.debug(f"Error checking pattern {pattern}: {e}")
