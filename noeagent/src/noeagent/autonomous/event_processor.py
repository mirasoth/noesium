"""Event processor for autonomous agents using BaseWatchdog pattern (RFC-1007).

The EventProcessor listens for AutonomousEvents, evaluates triggers, and creates goals.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, ClassVar

from bubus import BaseEvent

from noesium.core.msgbus import BaseWatchdog

from .event_queue import EventQueue
from .event_system import AutonomousEvent
from .goal_engine import GoalEngine
from .trigger import Trigger

if TYPE_CHECKING:
    from noesium.core.msgbus import EventBus


logger = logging.getLogger(__name__)


class EventProcessor(BaseWatchdog[Any]):
    """Event processor using BaseWatchdog pattern (RFC-1007 Section 9).

    Listens for AutonomousEvents, evaluates triggers, and creates goals
    in the Goal Engine.

    Example:
        event_processor = EventProcessor(
            event_bus=event_bus,
            goal_engine=goal_engine,
            triggers=[
                Trigger(
                    id="github-issue",
                    event_type="github.issue.created",
                    goal_template="Review GitHub issue {issue_id}",
                    priority=70,
                ),
            ],
        )
        event_processor.attach_to_processor()
    """

    LISTENS_TO: ClassVar[list[type[BaseEvent[Any]]]] = [AutonomousEvent]
    EMITS: ClassVar[list[type[BaseEvent[Any]]]] = []

    def __init__(
        self,
        event_bus: EventBus,
        goal_engine: GoalEngine,
        triggers: list[Trigger],
    ):
        """Initialize EventProcessor.

        Args:
            event_bus: Event bus for event dispatch
            goal_engine: Goal engine for creating goals
            triggers: List of trigger rules to evaluate
        """

        # Create a minimal event processor interface for BaseWatchdog
        class _ProcessorInterface:
            def __init__(self, bus: EventBus):
                self.event_bus = bus
                self.logger = logger

        processor = _ProcessorInterface(event_bus)

        super().__init__(event_bus=event_bus, event_processor=processor)

        self.goal_engine = goal_engine
        self.triggers = triggers

        # Sequential event processing (RFC-1007 Section 10)
        self._event_queue = EventQueue()
        self._running = False
        self._processing_task: asyncio.Task[None] | None = None

        logger.info(f"EventProcessor initialized with {len(triggers)} triggers")

    async def on_AutonomousEvent(self, event: AutonomousEvent) -> None:
        """Handle incoming AutonomousEvent by enqueueing for sequential processing.

        This method is non-blocking - it only enqueues the event.
        The actual processing happens in the _process_loop().

        Args:
            event: Autonomous event to enqueue
        """
        await self._event_queue.enqueue(event)
        logger.debug(f"Enqueued event {event.id[:8]}: {event.type} from {event.source}")

    async def _process_event(self, event: AutonomousEvent) -> None:
        """Process a single event by evaluating triggers.

        Args:
            event: Event to process
        """
        logger.debug(f"Processing event {event.id[:8]}: {event.type} from {event.source}")

        for trigger in self.triggers:
            try:
                if trigger.evaluate(event):
                    # Create goal from trigger
                    description = trigger.create_goal_description(event)
                    goal = await self.goal_engine.create_goal(
                        description=description,
                        priority=trigger.priority,
                    )

                    logger.info(f"Trigger '{trigger.id}' fired: created goal {goal.id[:8]} " f"from event {event.type}")
            except Exception as e:
                logger.error(
                    f"Error evaluating trigger '{trigger.id}' for event {event.id[:8]}: {e}",
                    exc_info=True,
                )

    async def _process_loop(self) -> None:
        """Sequential event processing loop.

        Continuously processes events from the queue while _running is True.
        """
        logger.info("EventProcessor processing loop started")

        while self._running:
            try:
                event = await self._event_queue.process_next()

                if event is not None:
                    await self._process_event(event)
                else:
                    # No events available, sleep briefly
                    await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                logger.info("EventProcessor processing loop cancelled")
                break

            except Exception as e:
                logger.error(f"Error in processing loop: {e}", exc_info=True)
                # Backoff on error
                await asyncio.sleep(1.0)

        logger.info("EventProcessor processing loop stopped")

    def attach_to_processor(self) -> None:
        """Attach watchdog to its event processor and start monitoring.

        Starts the event processing loop for sequential event handling.
        """
        # Call parent to register event handlers
        super().attach_to_processor()

        # Start the processing loop
        self._running = True
        self._processing_task = asyncio.create_task(self._process_loop())
        logger.info("EventProcessor attached and processing loop started")

    async def stop_processing(self) -> None:
        """Stop the event processing loop and clean up.

        Waits for the processing task to complete.
        """
        logger.info("Stopping EventProcessor processing loop")
        self._running = False

        if self._processing_task is not None:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
            self._processing_task = None

        # Clear any pending events
        self._event_queue.clear()
        logger.info("EventProcessor stopped and queue cleared")
