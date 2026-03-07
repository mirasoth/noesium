"""Cognitive Loop for autonomous execution (RFC-1005 Section 7).

The Cognitive Loop is the continuous runtime loop that drives autonomous execution.
It repeatedly selects a goal, generates reasoning, performs actions, and updates memory.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from noesium.core.autonomous import Goal, GoalEngine

if TYPE_CHECKING:
    from noeagent.agent import NoeAgent

    from noesium.core.capability.registry import CapabilityRegistry
    from noesium.core.memory.provider_manager import ProviderMemoryManager


logger = logging.getLogger(__name__)


class CognitiveLoop:
    """Continuous cognitive loop for autonomous execution (RFC-1005 Section 7).

    The loop executes the following cycle:
    1. Get next goal from Goal Engine
    2. Project memory context for goal
    3. Agent kernel reasoning step
    4. Execute decision (tool/subagent call)
    5. Update memory with observation

    Each iteration is called a "tick" (typical duration: 5-30 seconds).

    Example:
        loop = CognitiveLoop(
            goal_engine=goal_engine,
            memory=memory_manager,
            agent_kernel=agent,
            capability_registry=registry,
            tick_interval=10.0,
        )
        await loop.run()
    """

    def __init__(
        self,
        goal_engine: GoalEngine,
        memory: ProviderMemoryManager,
        agent_kernel: NoeAgent,
        capability_registry: CapabilityRegistry,
        tick_interval: float = 5.0,
    ):
        """Initialize Cognitive Loop.

        Args:
            goal_engine: Goal engine for goal selection
            memory: Memory manager for context projection
            agent_kernel: Agent kernel for reasoning
            capability_registry: Capability registry for execution
            tick_interval: Seconds between ticks (default: 5.0)
        """
        self.goal_engine = goal_engine
        self.memory = memory
        self.agent_kernel = agent_kernel
        self.capability_registry = capability_registry
        self.tick_interval = tick_interval
        self._running = False
        self._current_goal: Goal | None = None

        logger.info(f"CognitiveLoop initialized with tick_interval={tick_interval}s")

    async def run(self) -> None:
        """Main cognitive loop: goal → context → decision → observation → memory.

        Runs continuously until stop() is called.
        """
        self._running = True
        logger.info("🧠 Cognitive loop started")

        while self._running:
            try:
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
        """Single iteration of the cognitive loop."""
        # 1. Get next goal
        goal = await self.goal_engine.next_goal()
        if not goal:
            logger.debug("No active goals - idle tick")
            return

        self._current_goal = goal
        logger.info(f"🎯 Processing goal: {goal.description} (priority={goal.priority})")

        try:
            # 2. Project memory context for this goal
            context = await self._project_memory(goal)

            # 3. Agent kernel reasoning step
            decision = await self._reason(goal, context)

            # 4. Execute decision (tool/subagent call)
            observation = await self._execute_decision(decision)

            # 5. Update memory
            await self._update_memory(goal, observation)

            # 6. Update goal status based on observation
            await self._evaluate_goal_progress(goal, observation)

        except Exception as e:
            logger.error(f"Error processing goal {goal.id[:8]}: {e}", exc_info=True)
            await self.goal_engine.fail_goal(goal.id, error=str(e))

        finally:
            self._current_goal = None

    async def _project_memory(self, goal: Goal) -> dict[str, Any]:
        """Project memory context for goal (RFC-1002 projection model).

        Retrieves relevant context from memory for reasoning.

        Args:
            goal: Goal to project context for

        Returns:
            Memory context dictionary
        """
        try:
            # Get persistent memory provider
            persistent_provider = self.memory.get_provider("persistent")

            # Search for relevant memories related to the goal
            # Use keywords from goal description for semantic search
            keywords = goal.description.lower().split()[:5]  # Top 5 keywords

            related_memories = []
            try:
                # Attempt semantic search if supported
                search_results = await persistent_provider.search(
                    query=" ".join(keywords),
                    limit=10,
                    content_types=["fact", "execution_trace", "goal"],
                )
                related_memories = [
                    {
                        "key": result.entry.key,
                        "value": result.entry.value,
                        "score": result.score,
                        "content_type": result.entry.content_type,
                    }
                    for result in search_results[:5]  # Top 5 relevant memories
                ]
            except Exception as search_error:
                logger.debug(f"Semantic search not available: {search_error}")

            # Get goal history
            goal_history = await persistent_provider.read(f"goal:{goal.id}")

            # Get execution traces for this goal
            execution_key = f"execution:{goal.id}"
            execution_trace = await persistent_provider.read(execution_key)

            context = {
                "goal_id": goal.id,
                "goal_description": goal.description,
                "goal_priority": goal.priority,
                "goal_status": goal.status,
                "related_memories": related_memories,
                "goal_history": goal_history.value if goal_history else None,
                "previous_execution": execution_trace.value if execution_trace else None,
            }

            logger.debug(
                f"Projected memory context for goal {goal.id[:8]} with {len(related_memories)} related memories"
            )
            return context

        except Exception as e:
            logger.error(f"Failed to project memory: {e}", exc_info=True)
            return {
                "goal_id": goal.id,
                "goal_description": goal.description,
                "goal_priority": goal.priority,
            }

    async def _reason(self, goal: Goal, context: dict[str, Any]) -> dict[str, Any]:
        """Agent kernel reasoning step.

        Uses the Agent Kernel to decide what action to take for the goal.

        Args:
            goal: Goal to reason about
            context: Memory context

        Returns:
            Decision dictionary with action to take
        """
        try:
            # Use the agent kernel's step method
            # The agent kernel performs reasoning and returns a decision
            # TODO: Define decision format with agent kernel
            decision = {
                "action": "think",  # or "tool_call", "subagent_call", etc.
                "goal_id": goal.id,
                "context": context,
                "reasoning": f"Processing goal: {goal.description}",
            }

            logger.debug(f"Agent kernel decision: {decision.get('action')}")
            return decision

        except Exception as e:
            logger.error(f"Agent kernel reasoning failed: {e}", exc_info=True)
            raise

    async def _execute_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        """Execute agent decision (tool call, subagent call, etc.).

        Args:
            decision: Decision from agent kernel

        Returns:
            Observation dictionary with execution results
        """
        action = decision.get("action", "think")

        try:
            if action == "tool_call":
                # Execute tool via capability registry
                tool_id = decision.get("tool_id")
                tool_input = decision.get("input", {})

                provider = await self.capability_registry.resolve(tool_id)
                result = await provider.invoke(tool_input)

                observation = {
                    "action": "tool_call",
                    "tool_id": tool_id,
                    "result": result,
                    "success": True,
                }

            elif action == "subagent_call":
                # Delegate to subagent
                subagent_type = decision.get("subagent_type")
                decision.get("task")

                # TODO: Implement subagent invocation
                observation = {
                    "action": "subagent_call",
                    "subagent_type": subagent_type,
                    "result": "Subagent execution not implemented",
                    "success": False,
                }

            elif action == "finish_goal":
                # Mark goal as completed
                observation = {
                    "action": "finish_goal",
                    "success": True,
                }

            else:
                # Default: thinking action
                observation = {
                    "action": "think",
                    "thoughts": decision.get("reasoning", ""),
                    "success": True,
                }

            logger.info(f"Executed action: {action} (success={observation.get('success')})")
            return observation

        except Exception as e:
            logger.error(f"Decision execution failed: {e}", exc_info=True)
            return {
                "action": action,
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

    async def _evaluate_goal_progress(self, goal: Goal, observation: dict[str, Any]) -> None:
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
        logger.info("Cognitive loop stop requested")

    @property
    def current_goal(self) -> Goal | None:
        """Get current goal being processed.

        Returns:
            Current goal or None if idle
        """
        return self._current_goal
