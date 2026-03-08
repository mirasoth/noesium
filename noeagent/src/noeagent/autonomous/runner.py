"""Autonomous mode runner for NoeAgent.

Provides the entry point for running NoeAgent in autonomous mode with
the Cognitive Loop, Goal Engine, and Event System.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bubus import EventBus
from noeagent.autonomous import (
    EventProcessor,
    GoalEngine,
    TimerEventSource,
    Trigger,
)
from noeagent.kernel import AgentKernel

from noesium.core.event.store import InMemoryEventStore

from .cognitive_loop import CognitiveLoop

if TYPE_CHECKING:
    from noeagent.agent import NoeAgent


logger = logging.getLogger(__name__)


class AutonomousRunner:
    """Runner for autonomous mode.

    Initializes and coordinates:
    - Goal Engine
    - Event Bus and Event Processor
    - Cognitive Loop
    - Event Sources (timer, filesystem, etc.)

    Example:
        agent = NoeAgent(...)
        runner = AutonomousRunner(agent)

        # Add initial goal
        await runner.goal_engine.create_goal("Monitor GitHub issues")

        # Start autonomous mode
        await runner.start()
    """

    def __init__(self, agent: NoeAgent, tick_interval: float = 10.0):
        """Initialize autonomous runner.

        Args:
            agent: NoeAgent instance
            tick_interval: Cognitive loop tick interval in seconds
        """
        self.agent = agent

        # Initialize event bus
        self.event_bus = EventBus()

        # Initialize event store
        self.event_store = InMemoryEventStore()

        # Get memory provider for goals
        # Try to get persistent provider, fallback to working memory
        try:
            goal_memory = agent.memory_manager.get_provider("persistent")
        except Exception:
            logger.warning("Persistent memory not available, using working memory")
            goal_memory = agent.memory_manager.get_provider("working")

        # Initialize Goal Engine
        self.goal_engine = GoalEngine(
            memory_provider=goal_memory,
            event_store=self.event_store,
            producer=agent.producer,
        )

        # Initialize Cognitive Loop (use AgentKernel for step(goal, context) interface)
        agent_kernel = AgentKernel(agent)
        self.cognitive_loop = CognitiveLoop(
            goal_engine=self.goal_engine,
            memory=agent.memory_manager,
            agent_kernel=agent_kernel,
            capability_registry=agent.capability_registry,
            tick_interval=tick_interval,
        )

        # Initialize Event Processor with default triggers
        self.triggers = self._create_default_triggers()
        self.event_processor = EventProcessor(
            event_bus=self.event_bus,
            goal_engine=self.goal_engine,
            triggers=self.triggers,
        )

        # Event sources
        self.timer_source: TimerEventSource | None = None

        logger.info("AutonomousRunner initialized")

    def _create_default_triggers(self) -> list[Trigger]:
        """Create default trigger rules.

        Returns:
            List of Trigger instances
        """
        triggers = [
            # Example: Timer triggers daily review
            Trigger(
                id="daily-review-trigger",
                event_type="timer",
                goal_template="Perform periodic system review",
                priority=30,
            ),
            # Example: GitHub issue created
            Trigger(
                id="github-issue-trigger",
                event_type="github.issue.created",
                goal_template="Review GitHub issue {issue_id} in {repo}",
                priority=70,
            ),
            # Example: File system change
            Trigger(
                id="filesystem-change-trigger",
                event_type="filesystem.change",
                goal_template="Process file change: {path}",
                priority=50,
            ),
        ]

        logger.info(f"Created {len(triggers)} default triggers")
        return triggers

    async def start(self) -> None:
        """Start autonomous mode.

        - Initializes goal engine
        - Starts event sources
        - Attaches event processor
        - Runs cognitive loop
        """
        logger.info("🚀 Starting autonomous mode...")

        # Initialize goal engine (load existing goals)
        await self.goal_engine.initialize()

        # Attach event processor to event bus
        self.event_processor.attach_to_processor()

        # Start timer event source (emit event every 5 minutes)
        self.timer_source = TimerEventSource(
            event_bus=self.event_bus,
            interval_seconds=300,
        )
        await self.timer_source.start()

        logger.info("✅ Autonomous mode started")

        # Run cognitive loop (blocks until stopped)
        await self.cognitive_loop.run()

    async def stop(self) -> None:
        """Stop autonomous mode.

        - Stops cognitive loop
        - Stops event sources
        - Cleans up resources
        """
        logger.info("🛑 Stopping autonomous mode...")

        # Stop cognitive loop
        self.cognitive_loop.stop()

        # Stop timer source
        if self.timer_source:
            self.timer_source.stop()

        logger.info("✅ Autonomous mode stopped")

    async def add_goal(self, description: str, priority: int = 50) -> None:
        """Add a goal to the goal engine.

        Args:
            description: Goal description
            priority: Goal priority (0-100)
        """
        await self.goal_engine.create_goal(description, priority=priority)
        logger.info(f"Added goal: {description} (priority={priority})")

    def add_trigger(self, trigger: Trigger) -> None:
        """Add a custom trigger rule.

        Args:
            trigger: Trigger to add
        """
        self.triggers.append(trigger)
        logger.info(f"Added trigger: {trigger.id}")


async def run_autonomous_mode(agent: NoeAgent, initial_goal: str | None = None) -> None:
    """Run NoeAgent in autonomous mode.

    Args:
        agent: NoeAgent instance
        initial_goal: Optional initial goal to add
    """
    runner = AutonomousRunner(agent)

    # Add initial goal if provided
    if initial_goal:
        await runner.add_goal(initial_goal, priority=70)

    try:
        await runner.start()
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
    except Exception as e:
        logger.error(f"Autonomous mode error: {e}", exc_info=True)
    finally:
        await runner.stop()
