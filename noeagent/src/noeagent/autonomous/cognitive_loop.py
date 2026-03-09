"""Cognitive Loop for autonomous execution (RFC-1005 Section 7).

The Cognitive Loop is the continuous runtime loop that drives autonomous execution.
It repeatedly selects a goal, generates reasoning, performs actions, and updates memory.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Any

from noeagent.autonomous.decision_schema import (
    CreateGoalDecision,
    Decision,
    DecisionAction,
    MemoryUpdateDecision,
    SubagentCallDecision,
    ToolCallDecision,
)
from noeagent.autonomous.goal_engine import Goal, GoalEngine, GoalStatus
from noeagent.autonomous.memory import MemoryProjector
from uuid_extensions import uuid7str

if TYPE_CHECKING:
    from noeagent.autonomous.kernel.agent_kernel import AgentKernel

    from noesium.core.agent.subagent import SubagentManager
    from noesium.core.capability.registry import CapabilityRegistry
    from noesium.core.memory.provider_manager import ProviderMemoryManager


logger = logging.getLogger(__name__)


@dataclass
class CognitiveLoopMetrics:
    """Metrics for cognitive loop execution (RFC-1005)."""

    total_ticks: int = 0
    successful_ticks: int = 0
    failed_ticks: int = 0
    idle_ticks: int = 0
    total_tick_duration_ms: float = 0.0
    last_tick_duration_ms: float = 0.0

    @property
    def avg_tick_duration_ms(self) -> float:
        """Average tick duration in milliseconds."""
        return self.total_tick_duration_ms / max(1, self.total_ticks)

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.total_ticks = 0
        self.successful_ticks = 0
        self.failed_ticks = 0
        self.idle_ticks = 0
        self.total_tick_duration_ms = 0.0
        self.last_tick_duration_ms = 0.0


class CognitiveLoop:
    """Continuous cognitive loop for autonomous execution (RFC-1005 Section 7).

    The loop executes the following cycle:
    1. Get next goal from Goal Engine
    2. Project memory context for goal
    3. Agent kernel reasoning step
    4. Execute decision (tool/subagent call)
    5. Update memory with observation

    Each iteration is called a "tick" (typical duration: 5-30 seconds).

    Features:
    - Pause/resume capability for controlled execution
    - Metrics collection for monitoring (tick duration, success/failure rates)
    - Subagent invocation via SubagentManager
    - Goal timeout checking before each tick

    Example:
        loop = CognitiveLoop(
            goal_engine=goal_engine,
            memory=memory_manager,
            agent_kernel=agent,
            capability_registry=registry,
            tick_interval=10.0,
            subagent_manager=subagent_manager,
        )
        await loop.run()
    """

    def __init__(
        self,
        goal_engine: GoalEngine,
        memory: ProviderMemoryManager,
        agent_kernel: AgentKernel,
        capability_registry: CapabilityRegistry,
        tick_interval: float = 5.0,
        subagent_manager: SubagentManager | None = None,
    ):
        """Initialize Cognitive Loop.

        Args:
            goal_engine: Goal engine for goal selection
            memory: Memory manager for context projection
            agent_kernel: Agent kernel for reasoning (RFC-1005 §8)
            capability_registry: Capability registry for execution
            tick_interval: Seconds between ticks (default: 5.0)
            subagent_manager: SubagentManager for subagent invocation (RFC-1005)
        """
        self.goal_engine = goal_engine
        self.memory = memory
        self.agent_kernel = agent_kernel
        self.capability_registry = capability_registry
        self.tick_interval = tick_interval
        self._running = False
        self._current_goal: Goal | None = None

        # Subagent support (RFC-1005)
        self._subagent_manager = subagent_manager
        self._session_id = uuid7str()

        # Pause/resume support (RFC-1005)
        self._paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially

        # Metrics collection (RFC-1005)
        self._metrics = CognitiveLoopMetrics()

        self.projector = MemoryProjector(memory)

        logger.info(f"CognitiveLoop initialized with tick_interval={tick_interval}s")

    async def run(self) -> None:
        """Main cognitive loop: goal -> context -> decision -> observation -> memory.

        Runs continuously until stop() is called. Supports pause/resume.
        """
        self._running = True
        logger.info("Cognitive loop started")

        while self._running:
            try:
                # Wait if paused (RFC-1005 pause/resume)
                await self._pause_event.wait()

                await self._tick()
                await asyncio.sleep(self.tick_interval)
            except asyncio.CancelledError:
                logger.info("Cognitive loop cancelled")
                break
            except Exception as e:
                logger.error(f"Cognitive loop error: {e}", exc_info=True)
                # Backoff on error
                await asyncio.sleep(self.tick_interval * 2)

        logger.info("Cognitive loop stopped")

    async def _tick(self) -> None:
        """Single iteration of the cognitive loop with metrics collection."""
        start_time = perf_counter()
        tick_success = False

        try:
            # Check for timed-out goals first (RFC-1006 timeout support)
            if hasattr(self.goal_engine, "check_timeouts"):
                await self.goal_engine.check_timeouts()

            goal = await self.goal_engine.next_goal()
            if not goal:
                logger.debug("No active goals - idle tick")
                self._metrics.idle_ticks += 1
                tick_success = True
                return

            self._current_goal = goal
            logger.info(
                f"Processing goal: {goal.description} (priority={goal.priority})"
            )

            try:
                context = await self.projector.project(goal)

                decision = await self._reason(goal, context)

                observation = await self._execute_decision(decision)

                await self._update_memory(goal, observation)

                await self._evaluate_goal_progress(goal, observation)

                tick_success = True

            except Exception as e:
                logger.error(f"Error processing goal {goal.id[:8]}: {e}", exc_info=True)
                await self.goal_engine.fail_goal(goal.id, error=str(e))

            finally:
                self._current_goal = None

        except Exception as e:
            logger.error(f"Tick error: {e}", exc_info=True)
            raise

        finally:
            # Update metrics (RFC-1005 metrics collection)
            duration_ms = (perf_counter() - start_time) * 1000
            self._metrics.total_ticks += 1
            self._metrics.total_tick_duration_ms += duration_ms
            self._metrics.last_tick_duration_ms = duration_ms
            if tick_success:
                self._metrics.successful_ticks += 1
            else:
                self._metrics.failed_ticks += 1

    async def _reason(self, goal: Goal, context: dict[str, Any]) -> Decision:
        """Agent kernel reasoning step.

        Uses the Agent Kernel to decide what action to take for the goal.

        Args:
            goal: Goal to reason about
            context: Memory context

        Returns:
            Typed Decision object with action to take
        """
        try:
            # Use the agent kernel's step method for reasoning
            decision = await self.agent_kernel.step(goal, context)

            logger.debug(f"Agent kernel decision: {decision.action}")
            return decision

        except Exception as e:
            logger.error(f"Agent kernel reasoning failed: {e}", exc_info=True)
            raise

    async def _execute_decision(self, decision: Decision) -> dict[str, Any]:
        """Execute agent decision (tool call, subagent call, etc.).

        Args:
            decision: Typed Decision from agent kernel

        Returns:
            Observation dictionary with execution results
        """
        try:
            if decision.action == DecisionAction.TOOL_CALL:
                # Execute tool via capability registry
                if isinstance(decision, ToolCallDecision):
                    tool_id = decision.tool_id
                    tool_input = decision.tool_input
                else:
                    tool_id = decision.tool_id
                    tool_input = decision.tool_input or {}

                provider = await self.capability_registry.resolve(tool_id)
                result = await provider.invoke(tool_input)

                observation = {
                    "action": "tool_call",
                    "tool_id": tool_id,
                    "result": result,
                    "success": True,
                }

            elif decision.action == DecisionAction.SUBAGENT_CALL:
                # Delegate to subagent via SubagentManager (RFC-1005)
                if isinstance(decision, SubagentCallDecision):
                    subagent_type = decision.subagent_type
                    subagent_task = decision.subagent_task
                else:
                    subagent_type = decision.subagent_type or "unknown"
                    subagent_task = decision.subagent_task or ""

                # Check if SubagentManager is available
                if self._subagent_manager is None:
                    observation = {
                        "action": "subagent_call",
                        "subagent_type": subagent_type,
                        "task": subagent_task,
                        "result": "SubagentManager not available",
                        "success": False,
                    }
                else:
                    # Invoke subagent via SubagentManager
                    from noesium.core.agent.subagent import (
                        SubagentContext,
                        SubagentEventType,
                        SubagentInvocationRequest,
                    )

                    request = SubagentInvocationRequest(
                        subagent_id=subagent_type, message=subagent_task
                    )
                    context = SubagentContext(
                        session_id=self._session_id,
                        parent_id="cognitive_loop",
                        depth=0,
                        max_depth=3,
                    )

                    result = ""
                    try:
                        async for event in self._subagent_manager.invoke_stream(
                            subagent_type, request, context
                        ):
                            if event.event_type == SubagentEventType.SUBAGENT_END:
                                result = event.detail or event.summary or ""
                            elif event.event_type == SubagentEventType.SUBAGENT_ERROR:
                                result = f"Error: {event.error_message}"

                        observation = {
                            "action": "subagent_call",
                            "subagent_type": subagent_type,
                            "task": subagent_task,
                            "result": result,
                            "success": True,
                        }
                    except Exception as e:
                        logger.error(f"Subagent invocation failed: {e}", exc_info=True)
                        observation = {
                            "action": "subagent_call",
                            "subagent_type": subagent_type,
                            "task": subagent_task,
                            "result": f"Subagent error: {e}",
                            "success": False,
                        }

            elif decision.action == DecisionAction.MEMORY_UPDATE:
                # Update memory with new information
                if isinstance(decision, MemoryUpdateDecision):
                    memory_key = decision.memory_key
                    memory_value = decision.memory_value
                    memory_content_type = decision.memory_content_type
                else:
                    memory_key = decision.memory_key or "unknown"
                    memory_value = decision.memory_value
                    memory_content_type = decision.memory_content_type or "fact"

                # Get working memory provider and write
                working_provider = self.memory.get_provider("working")
                await working_provider.write(
                    key=memory_key,
                    value=memory_value,
                    content_type=memory_content_type,
                )

                observation = {
                    "action": "memory_update",
                    "key": memory_key,
                    "success": True,
                }

            elif decision.action == DecisionAction.GOAL_UPDATE:
                # Update goal status
                new_status_str = decision.new_goal_status
                if new_status_str:
                    # Convert string to GoalStatus enum
                    new_status = GoalStatus(new_status_str)
                    await self.goal_engine.update_goal(decision.goal_id, new_status)

                observation = {
                    "action": "goal_update",
                    "new_status": new_status_str,
                    "success": True,
                }

            elif decision.action == DecisionAction.FINISH_GOAL:
                # Mark goal as completed
                observation = {
                    "action": "finish_goal",
                    "success": True,
                }

            elif decision.action == DecisionAction.CREATE_GOAL:
                # Create new goal (self-generated or sub-goal)
                if isinstance(decision, CreateGoalDecision):
                    goal_description = decision.goal_description
                    goal_priority = decision.goal_priority
                    parent_goal_id = decision.parent_goal_id
                else:
                    goal_description = decision.goal_description or "New goal"
                    goal_priority = decision.goal_priority or 50
                    parent_goal_id = decision.parent_goal_id

                # Create new goal with parent linkage if provided
                new_goal = await self.goal_engine.create_goal(
                    description=goal_description,
                    priority=goal_priority,
                    parent_goal_id=parent_goal_id or decision.goal_id,
                )

                observation = {
                    "action": "create_goal",
                    "new_goal_id": new_goal.id,
                    "description": goal_description,
                    "priority": goal_priority,
                    "parent_id": parent_goal_id,
                    "success": True,
                }

            else:
                # Unknown action
                observation = {
                    "action": str(decision.action),
                    "success": False,
                    "error": f"Unknown action type: {decision.action}",
                }

            logger.info(
                f"Executed action: {decision.action} (success={observation.get('success')})"
            )
            return observation

        except Exception as e:
            logger.error(f"Decision execution failed: {e}", exc_info=True)
            return {
                "action": str(decision.action),
                "error": str(e),
                "success": False,
            }

    async def _update_memory(self, goal: Goal, observation: dict[str, Any]) -> None:
        """Store observation in memory.

        Args:
            goal: Goal being processed
            observation: Execution observation
        """
        try:
            # Get working memory provider
            working_provider = self.memory.get_provider("working")

            # Store execution trace
            await working_provider.write(
                key=f"execution:{goal.id}",
                value={
                    "goal_id": goal.id,
                    "goal_description": goal.description,
                    "observation": observation,
                },
                content_type="execution_trace",
            )

            logger.debug(f"Updated memory for goal {goal.id[:8]}")

        except Exception as e:
            logger.error(f"Failed to update memory: {e}", exc_info=True)

    async def _evaluate_goal_progress(
        self, goal: Goal, observation: dict[str, Any]
    ) -> None:
        """Evaluate goal progress and update status.

        Args:
            goal: Goal being processed
            observation: Execution observation
        """
        # Simple heuristic: if observation indicates completion, complete goal
        if observation.get("action") == "finish_goal" and observation.get("success"):
            await self.goal_engine.complete_goal(goal.id)
            logger.info(f"✅ Goal completed: {goal.description}")

        # If observation indicates failure, fail goal
        elif not observation.get("success", True):
            error = observation.get("error", "Unknown error")
            await self.goal_engine.fail_goal(goal.id, error=error)

        # Otherwise, goal remains active for next tick

    def stop(self) -> None:
        """Stop the cognitive loop."""
        self._running = False
        # Also resume if paused, so the loop can exit
        self._pause_event.set()
        logger.info("Cognitive loop stop requested")

    def pause(self) -> None:
        """Pause the cognitive loop after current tick completes (RFC-1005)."""
        self._paused = True
        self._pause_event.clear()
        logger.info("Cognitive loop paused")

    def resume(self) -> None:
        """Resume the paused cognitive loop (RFC-1005)."""
        self._paused = False
        self._pause_event.set()
        logger.info("Cognitive loop resumed")

    @property
    def is_paused(self) -> bool:
        """Check if the cognitive loop is paused."""
        return self._paused

    @property
    def is_running(self) -> bool:
        """Check if the cognitive loop is running."""
        return self._running

    @property
    def metrics(self) -> CognitiveLoopMetrics:
        """Get cognitive loop metrics (RFC-1005)."""
        return self._metrics

    @property
    def current_goal(self) -> Goal | None:
        """Get current goal being processed.

        Returns:
            Current goal or None if idle
        """
        return self._current_goal
