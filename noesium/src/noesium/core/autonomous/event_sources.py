"""Event sources for autonomous agents (RFC-1007 Section 7).

Event sources emit AutonomousEvents to the EventBus, enabling reactive behavior.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .event_system import AutonomousEvent

if TYPE_CHECKING:
    from noesium.core.msgbus import EventBus


logger = logging.getLogger(__name__)


class TimerEventSource:
    """Timer-based event source (RFC-1007 Section 7.1).

    Emits periodic timer events at a configurable interval.

    Example:
        timer = TimerEventSource(event_bus=event_bus, interval_seconds=300)
        await timer.start()  # Emits event every 5 minutes
    """

    def __init__(self, event_bus: EventBus, interval_seconds: int):
        """Initialize timer event source.

        Args:
            event_bus: Event bus for emitting events
            interval_seconds: Interval between timer events (in seconds)
        """
        self.event_bus = event_bus
        self.interval = interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start emitting timer events."""
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info(f"TimerEventSource started: interval={self.interval}s")

    async def _run(self) -> None:
        """Emit timer events at interval."""
        while self._running:
            try:
                await asyncio.sleep(self.interval)

                event = AutonomousEvent(
                    type="timer",
                    source="timer_service",
                    payload={"interval": f"{self.interval}s"},
                )

                self.event_bus.dispatch(event)
                logger.debug(f"Emitted timer event {event.id[:8]}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Timer error: {e}", exc_info=True)

    def stop(self) -> None:
        """Stop emitting timer events."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("TimerEventSource stopped")


class FileSystemEventSource:
    """File system watcher event source (RFC-1007 Section 7.2).

    Monitors a directory for file system changes and emits events.

    Note: This is a simplified implementation. For production use,
    integrate with watchdog library or inotify for efficient monitoring.
    """

    def __init__(self, event_bus: EventBus, watch_path: str, poll_interval: int = 5):
        """Initialize filesystem event source.

        Args:
            event_bus: Event bus for emitting events
            watch_path: Directory path to monitor
            poll_interval: Polling interval in seconds (default: 5)
        """
        self.event_bus = event_bus
        self.watch_path = Path(watch_path)
        self.poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None
        self._known_files: set[str] = set()

    async def start(self) -> None:
        """Start watching file system."""
        if not self.watch_path.exists():
            logger.warning(f"Watch path does not exist: {self.watch_path}")
            return

        # Initialize known files
        self._known_files = set(self._list_files())

        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info(f"FileSystemEventSource started: watching {self.watch_path}")

    def _list_files(self) -> list[str]:
        """List files in watch directory."""
        try:
            return [str(p) for p in self.watch_path.rglob("*") if p.is_file()]
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []

    async def _run(self) -> None:
        """Poll for file system changes."""
        while self._running:
            try:
                await asyncio.sleep(self.poll_interval)

                current_files = set(self._list_files())

                # Detect new files
                new_files = current_files - self._known_files
                for file_path in new_files:
                    event = AutonomousEvent(
                        type="filesystem.change",
                        source="filesystem_watcher",
                        payload={
                            "path": file_path,
                            "action": "create",
                        },
                    )
                    self.event_bus.dispatch(event)
                    logger.debug(f"Detected new file: {file_path}")

                # Detect deleted files
                deleted_files = self._known_files - current_files
                for file_path in deleted_files:
                    event = AutonomousEvent(
                        type="filesystem.change",
                        source="filesystem_watcher",
                        payload={
                            "path": file_path,
                            "action": "delete",
                        },
                    )
                    self.event_bus.dispatch(event)
                    logger.debug(f"Detected deleted file: {file_path}")

                self._known_files = current_files

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"FileSystem watcher error: {e}", exc_info=True)

    def stop(self) -> None:
        """Stop watching file system."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("FileSystemEventSource stopped")


class WebhookEventSource:
    """Webhook-based event source for external integrations.

    Provides an interface for receiving events from external services
    (e.g., GitHub webhooks, Slack events).

    Example:
        webhook = WebhookEventSource(event_bus=event_bus)
        webhook.receive_event(
            type="github.issue.created",
            source="github_webhook",
            payload={"repo": "myrepo", "issue_id": 123}
        )
    """

    def __init__(self, event_bus: EventBus):
        """Initialize webhook event source.

        Args:
            event_bus: Event bus for emitting events
        """
        self.event_bus = event_bus
        logger.info("WebhookEventSource initialized")

    def receive_event(
        self,
        type: str,
        source: str,
        payload: dict[str, any],
    ) -> AutonomousEvent:
        """Receive and emit an external event.

        Args:
            type: Event type
            source: Event source
            payload: Event payload

        Returns:
            Created AutonomousEvent
        """
        event = AutonomousEvent(
            type=type,
            source=source,
            payload=payload,
        )

        self.event_bus.dispatch(event)
        logger.info(f"Received webhook event {event.id[:8]}: {type} from {source}")

        return event
