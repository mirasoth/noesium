"""Autonomous Goal Engine with deterministic scheduling (RFC-1006).

The Goal Engine manages goal lifecycle and scheduling. It does NOT perform reasoning.
All reasoning remains inside the Agent Kernel.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from noesium.core.event.envelope import AgentRef, TraceContext
from noesium.core.event.store import EventStore

from .events import GoalCompleted, GoalCreated, GoalFailed, GoalUpdated
from .models import Goal, GoalStatus

if TYPE_CHECKING:
    from noesium.core.memory.provider import MemoryProvider

logger = logging.getLogger(__name__)


class GoalEngine:
    """Autonomous Goal Engine (RFC-1006).

    Manages goal lifecycle and deterministic scheduling.

    Scheduling Policy:
        - Priority: higher priority goals selected first
        - Tie-breaker: oldest goal (earliest created_at) selected first
        - Combined sort: (priority DESC, created_at ASC)

    Storage:
        - Goals persist in MemoryProvider with key: "goal:{goal_id}"
        - In-memory priority queue for fast access

    The Goal Engine does NOT perform reasoning. It only manages goal state.
    """

    def __init__(
        self,
        memory_provider: MemoryProvider,
        event_store: EventStore | None = None,
        producer: AgentRef | None = None,
    ):
        """Initialize Goal Engine.

        Args:
            memory_provider: Memory provider for goal persistence
            event_store: Optional event store for emitting domain events
            producer: Optional producer identity for events
        """
        self._storage = memory_provider
        self._event_store = event_store
        self._producer = producer or AgentRef(agent_id="goal_engine", agent_type="system")
        self._trace = TraceContext()
        self._queue: list[Goal] = []
        self._goals_by_id: dict[str, Goal] = {}
        logger.info("Goal Engine initialized")

    async def _load_from_storage(self) -> None:
        """Load existing goals from memory provider."""
        try:
            keys = await self._storage.list_keys(prefix="goal:")
            for key in keys:
                entry = await self._storage.read(key)
                if entry and entry.value:
                    goal = Goal(**entry.value)
                    self._goals_by_id[goal.id] = goal
                    if goal.status in (GoalStatus.PENDING, GoalStatus.ACTIVE, GoalStatus.BLOCKED):
                        self._queue.append(goal)

            self._sort_queue()
            logger.info(f"Loaded {len(self._goals_by_id)} goals from storage, {len(self._queue)} active")
        except Exception as e:
            logger.error(f"Failed to load goals from storage: {e}", exc_info=True)

    def _sort_queue(self) -> None:
        """Sort queue by (priority DESC, created_at ASC) for deterministic scheduling."""
        self._queue.sort(key=lambda g: (-g.priority, g.created_at))

    async def _emit_event(self, event: GoalCreated | GoalUpdated | GoalCompleted | GoalFailed) -> None:
        """Emit domain event to event store if available."""
        if self._event_store is None:
            return

        try:
            envelope = event.to_envelope(producer=self._producer, trace=self._trace)
            await self._event_store.append(envelope)
        except Exception:
            logger.debug("Failed to emit goal event to EventStore", exc_info=True)

    async def create_goal(
        self,
        description: str,
        priority: int = 50,
        parent_goal_id: str | None = None,
    ) -> Goal:
        """Create a new goal.

        Args:
            description: Human-readable goal description
            priority: Goal priority (0-100, higher = more important)
            parent_goal_id: Optional parent goal for hierarchical goals

        Returns:
            Created goal instance
        """
        goal = Goal(
            description=description,
            priority=priority,
            parent_goal_id=parent_goal_id,
            status=GoalStatus.PENDING,
        )

        # Persist to memory
        await self._storage.write(
            key=f"goal:{goal.id}",
            value=goal.model_dump(),
            content_type="goal",
            metadata={"priority": priority, "status": goal.status},
        )

        # Update in-memory state
        self._goals_by_id[goal.id] = goal
        self._queue.append(goal)
        self._sort_queue()

        # Emit event
        await self._emit_event(
            GoalCreated(
                goal_id=goal.id,
                description=description,
                priority=priority,
            )
        )

        logger.info(f"Created goal {goal.id[:8]}: {description} (priority={priority})")
        return goal

    async def next_goal(self) -> Goal | None:
        """Get next goal for Cognitive Loop execution.

        Returns the highest priority goal that is PENDING or ACTIVE.
        Uses deterministic scheduling: (priority DESC, created_at ASC).

        Returns:
            Next goal to execute, or None if no active goals
        """
        # Filter for executable goals (PENDING or ACTIVE)
        executable = [g for g in self._queue if g.status in (GoalStatus.PENDING, GoalStatus.ACTIVE)]

        if not executable:
            logger.debug("No executable goals available")
            return None

        # Queue is already sorted, return first executable goal
        next_goal = executable[0]

        # Update status to ACTIVE if PENDING
        if next_goal.status == GoalStatus.PENDING:
            await self.update_goal(next_goal.id, GoalStatus.ACTIVE)

        logger.info(f"Next goal: {next_goal.id[:8]} (priority={next_goal.priority})")
        return next_goal

    async def update_goal(self, goal_id: str, status: GoalStatus) -> Goal:
        """Update goal status.

        Args:
            goal_id: Goal ID to update
            status: New status

        Returns:
            Updated goal instance

        Raises:
            ValueError: If goal not found
        """
        goal = self._goals_by_id.get(goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")

        old_status = goal.status
        goal.status = status
        goal.updated_at = datetime.now(tz=timezone.utc)

        # Persist update
        await self._storage.write(
            key=f"goal:{goal.id}",
            value=goal.model_dump(),
            content_type="goal",
            metadata={"priority": goal.priority, "status": status},
        )

        # Update queue (remove completed/failed goals)
        if status in (GoalStatus.COMPLETED, GoalStatus.FAILED):
            self._queue = [g for g in self._queue if g.id != goal_id]
        else:
            # Update in queue
            for i, g in enumerate(self._queue):
                if g.id == goal_id:
                    self._queue[i] = goal
                    break
            self._sort_queue()

        # Emit event
        await self._emit_event(
            GoalUpdated(
                goal_id=goal_id,
                old_status=old_status.value if isinstance(old_status, GoalStatus) else old_status,
                new_status=status.value if isinstance(status, GoalStatus) else status,
            )
        )

        logger.info(f"Updated goal {goal_id[:8]}: {old_status.value} → {status.value}")
        return goal

    async def complete_goal(self, goal_id: str) -> Goal:
        """Mark goal as completed.

        Args:
            goal_id: Goal ID to complete

        Returns:
            Completed goal instance
        """
        goal = await self.update_goal(goal_id, GoalStatus.COMPLETED)

        await self._emit_event(
            GoalCompleted(
                goal_id=goal_id,
                description=goal.description,
            )
        )

        logger.info(f"Completed goal {goal_id[:8]}: {goal.description}")
        return goal

    async def fail_goal(self, goal_id: str, error: str = "") -> Goal:
        """Mark goal as failed.

        Args:
            goal_id: Goal ID to fail
            error: Optional error message

        Returns:
            Failed goal instance
        """
        goal = await self.update_goal(goal_id, GoalStatus.FAILED)

        await self._emit_event(
            GoalFailed(
                goal_id=goal_id,
                description=goal.description,
                error=error,
            )
        )

        logger.warning(f"Failed goal {goal_id[:8]}: {goal.description}" + (f" - {error}" if error else ""))
        return goal

    async def list_goals(self, status: GoalStatus | None = None) -> list[Goal]:
        """List all goals, optionally filtered by status.

        Args:
            status: Optional status filter

        Returns:
            List of goals
        """
        if status:
            return [g for g in self._goals_by_id.values() if g.status == status]

        return list(self._goals_by_id.values())

    async def get_goal(self, goal_id: str) -> Goal | None:
        """Get goal by ID.

        Args:
            goal_id: Goal ID

        Returns:
            Goal instance or None if not found
        """
        return self._goals_by_id.get(goal_id)

    async def initialize(self) -> None:
        """Initialize goal engine by loading existing goals from storage."""
        await self._load_from_storage()
