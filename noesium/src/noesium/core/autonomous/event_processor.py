"""Event processor for autonomous agents using BaseWatchdog pattern (RFC-1007).

The EventProcessor listens for AutonomousEvents, evaluates triggers, and creates goals.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from bubus import BaseEvent

from noesium.core.msgbus import BaseWatchdog

from .event_system import AutonomousEvent
from .trigger import Trigger

if TYPE_CHECKING:
    from noesium.core.msgbus import EventBus

    from .goal_engine import GoalEngine


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

        logger.info(f"EventProcessor initialized with {len(triggers)} triggers")

    async def on_AutonomousEvent(self, event: AutonomousEvent) -> None:
        """Handle incoming AutonomousEvent.

        Evaluates all triggers and creates goals for matching triggers.

        Args:
            event: Autonomous event to process
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
