"""Event sources for autonomous agents (RFC-1007 Section 7).

Event sources emit AutonomousEvents to the EventBus, enabling reactive behavior.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .event_system import AutonomousEvent

if TYPE_CHECKING:
    from noesium.core.msgbus import EventBus


logger = logging.getLogger(__name__)


# Try to import watchdog for native file system events (RFC-1007)
try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object  # type: ignore


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
        payload: dict[str, Any],
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


class _WatchdogEventHandler(FileSystemEventHandler):
    """Internal handler for watchdog events (RFC-1007)."""

    def __init__(self, event_bus: EventBus):
        """Initialize handler.

        Args:
            event_bus: Event bus to dispatch events to
        """
        super().__init__()
        self.event_bus = event_bus

    def _emit(self, action: str, path: str) -> None:
        """Emit filesystem event to event bus."""
        event = AutonomousEvent(
            type="filesystem.change",
            source="watchdog",
            payload={"path": path, "action": action},
        )
        self.event_bus.dispatch(event)
        logger.debug(f"Watchdog event: {action} {path}")

    def on_created(self, event: Any) -> None:
        """Handle file/directory creation."""
        if not event.is_directory:
            self._emit("create", event.src_path)

    def on_deleted(self, event: Any) -> None:
        """Handle file/directory deletion."""
        if not event.is_directory:
            self._emit("delete", event.src_path)

    def on_modified(self, event: Any) -> None:
        """Handle file/directory modification."""
        if not event.is_directory:
            self._emit("modify", event.src_path)

    def on_moved(self, event: Any) -> None:
        """Handle file/directory move/rename."""
        if not event.is_directory:
            self._emit("move", event.dest_path)


class WatchdogFileSystemEventSource:
    """Native file system watcher using watchdog library (RFC-1007 Section 7.2).

    Uses native OS file system events (inotify on Linux, FSEvents on macOS,
    ReadDirectoryChangesW on Windows) for efficient file monitoring.

    Requires the watchdog package: pip install watchdog

    Example:
        watcher = WatchdogFileSystemEventSource(
            event_bus=event_bus,
            watch_path="/path/to/watch",
            recursive=True,
        )
        await watcher.start()
    """

    def __init__(
        self,
        event_bus: EventBus,
        watch_path: str,
        recursive: bool = True,
    ):
        """Initialize watchdog event source.

        Args:
            event_bus: Event bus for emitting events
            watch_path: Directory path to monitor
            recursive: Whether to monitor subdirectories (default: True)

        Raises:
            ImportError: If watchdog package is not installed
        """
        if not WATCHDOG_AVAILABLE:
            raise ImportError(
                "watchdog package required for WatchdogFileSystemEventSource. " "Install with: pip install watchdog"
            )

        self.event_bus = event_bus
        self.watch_path = Path(watch_path)
        self.recursive = recursive
        self._observer: Any = None
        self._running = False

    async def start(self) -> None:
        """Start watching file system using native events."""
        if not self.watch_path.exists():
            logger.warning(f"Watch path does not exist: {self.watch_path}")
            return

        handler = _WatchdogEventHandler(self.event_bus)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.watch_path), recursive=self.recursive)
        self._observer.start()
        self._running = True

        logger.info(
            f"WatchdogFileSystemEventSource started: watching {self.watch_path} " f"(recursive={self.recursive})"
        )

    def stop(self) -> None:
        """Stop watching file system."""
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        logger.info("WatchdogFileSystemEventSource stopped")

    @property
    def is_running(self) -> bool:
        """Check if the watcher is running."""
        return self._running


def get_filesystem_event_source(
    event_bus: EventBus,
    watch_path: str,
    prefer_watchdog: bool = True,
    poll_interval: int = 5,
    recursive: bool = True,
) -> FileSystemEventSource | WatchdogFileSystemEventSource:
    """Factory function to get the best available filesystem event source (RFC-1007).

    Returns WatchdogFileSystemEventSource if watchdog is available and preferred,
    otherwise falls back to polling-based FileSystemEventSource.

    Args:
        event_bus: Event bus for emitting events
        watch_path: Directory path to monitor
        prefer_watchdog: Prefer watchdog if available (default: True)
        poll_interval: Polling interval for fallback (default: 5 seconds)
        recursive: Monitor subdirectories (default: True)

    Returns:
        FileSystemEventSource or WatchdogFileSystemEventSource instance
    """
    if prefer_watchdog and WATCHDOG_AVAILABLE:
        logger.info("Using watchdog-based file system monitoring")
        return WatchdogFileSystemEventSource(
            event_bus=event_bus,
            watch_path=watch_path,
            recursive=recursive,
        )
    else:
        if prefer_watchdog:
            logger.info(
                "watchdog not available, falling back to polling-based monitoring. "
                "Install watchdog for better performance: pip install watchdog"
            )
        return FileSystemEventSource(
            event_bus=event_bus,
            watch_path=watch_path,
            poll_interval=poll_interval,
        )
