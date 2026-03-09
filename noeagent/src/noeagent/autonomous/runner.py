"""Autonomous mode runner for NoeAgent.

Provides the entry point for running NoeAgent in autonomous mode with
the Cognitive Loop, Goal Engine, and Event System.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bubus import EventBus
from noeagent.autonomous.event_processor import EventProcessor
from noeagent.autonomous.event_sources import (
    WATCHDOG_AVAILABLE,
    FileSystemEventSource,
    TimerEventSource,
    WatchdogFileSystemEventSource,
    get_filesystem_event_source,
)
from noeagent.autonomous.goal_engine import GoalEngine
from noeagent.autonomous.kernel.agent_kernel import AgentKernel
from noeagent.autonomous.trigger import Trigger

from noesium.core.event.store import InMemoryEventStore

from .cognitive_loop import CognitiveLoop, CognitiveLoopMetrics

if TYPE_CHECKING:
    from noeagent.agent import NoeAgent


logger = logging.getLogger(__name__)


class AutonomousRunner:
    """Runner for autonomous mode (RFC-1005, RFC-1006, RFC-1007).

    Initializes and coordinates:
    - Goal Engine (with dependencies, timeouts, retry policy)
    - Event Bus and Event Processor (with deduplication)
    - Cognitive Loop (with pause/resume, metrics, subagent support)
    - Event Sources (timer, filesystem with watchdog support)

    Example:
        agent = NoeAgent(...)
        runner = AutonomousRunner(agent)

        # Add initial goal with deadline
        from datetime import datetime, timedelta, timezone
        deadline = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        await runner.goal_engine.create_goal(
            "Monitor GitHub issues",
            deadline=deadline,
        )

        # Start autonomous mode
        await runner.start()
    """

    def __init__(
        self,
        agent: NoeAgent,
        tick_interval: float = 10.0,
        watch_path: str | None = None,
        prefer_watchdog: bool = True,
    ):
        """Initialize autonomous runner.

        Args:
            agent: NoeAgent instance
            tick_interval: Cognitive loop tick interval in seconds
            watch_path: Optional directory path to watch for filesystem events
            prefer_watchdog: Use watchdog library if available (default: True)
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

        # Initialize Goal Engine (RFC-1006)
        self.goal_engine = GoalEngine(
            memory_provider=goal_memory,
            event_store=self.event_store,
            producer=agent.producer,
        )

        # Initialize Cognitive Loop with SubagentManager (RFC-1005)
        agent_kernel = AgentKernel(agent)
        self.cognitive_loop = CognitiveLoop(
            goal_engine=self.goal_engine,
            memory=agent.memory_manager,
            agent_kernel=agent_kernel,
            capability_registry=agent.capability_registry,
            tick_interval=tick_interval,
            subagent_manager=agent._subagent_manager,  # Pass SubagentManager for subagent calls
        )

        # Initialize Event Processor with default triggers (RFC-1007)
        self.triggers = self._create_default_triggers()
        self.event_processor = EventProcessor(
            event_bus=self.event_bus,
            goal_engine=self.goal_engine,
            triggers=self.triggers,
        )

        # Event sources
        self.timer_source: TimerEventSource | None = None
        self.fs_source: FileSystemEventSource | WatchdogFileSystemEventSource | None = (
            None
        )
        self._watch_path = watch_path
        self._prefer_watchdog = prefer_watchdog

        logger.info(
            f"AutonomousRunner initialized (tick_interval={tick_interval}s, "
            f"watchdog={'available' if WATCHDOG_AVAILABLE else 'not available'})"
        )

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
        - Starts event sources (timer, filesystem)
        - Attaches event processor
        - Runs cognitive loop
        """
        logger.info("Starting autonomous mode...")

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

        # Start filesystem watcher if path configured (RFC-1007)
        if self._watch_path:
            self.fs_source = get_filesystem_event_source(
                event_bus=self.event_bus,
                watch_path=self._watch_path,
                prefer_watchdog=self._prefer_watchdog,
            )
            await self.fs_source.start()

        logger.info("Autonomous mode started")

        # Run cognitive loop (blocks until stopped)
        await self.cognitive_loop.run()

    async def stop(self) -> None:
        """Stop autonomous mode.

        - Stops cognitive loop
        - Stops event sources
        - Cleans up resources
        """
        logger.info("Stopping autonomous mode...")

        # Stop cognitive loop
        self.cognitive_loop.stop()

        # Stop event processor
        await self.event_processor.stop_processing()

        # Stop timer source
        if self.timer_source:
            self.timer_source.stop()

        # Stop filesystem watcher
        if self.fs_source:
            self.fs_source.stop()

        logger.info("Autonomous mode stopped")

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

    def pause(self) -> None:
        """Pause the cognitive loop (RFC-1005)."""
        self.cognitive_loop.pause()

    def resume(self) -> None:
        """Resume the cognitive loop (RFC-1005)."""
        self.cognitive_loop.resume()

    @property
    def is_paused(self) -> bool:
        """Check if cognitive loop is paused."""
        return self.cognitive_loop.is_paused

    @property
    def metrics(self) -> CognitiveLoopMetrics:
        """Get cognitive loop metrics (RFC-1005)."""
        return self.cognitive_loop.metrics


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
