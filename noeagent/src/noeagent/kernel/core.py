"""Agent Kernel component (RFC-1005 Section 8).

The Agent Kernel is the reasoning engine that produces executable decisions.
It wraps a NoeAgent instance and exposes a clean step-based interface for
the Cognitive Loop to invoke.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from noeagent.autonomous import Goal
from noeagent.autonomous.decision_schema import (
    Decision,
    DecisionAction,
)

if TYPE_CHECKING:
    from noeagent.agent import NoeAgent

logger = logging.getLogger(__name__)


class AgentKernel:
    """Reasoning engine that produces executable decisions (RFC-1005 §8).

    The Agent Kernel is the cognitive core of the autonomous architecture.
    It performs reasoning, planning, and decision-making to determine
    what actions to take for a given goal.

    The kernel exposes a simple step-based interface:
        step(goal, context) -> Decision

    Each step produces a decision that the Cognitive Loop executes.
    The decision can be:
    - tool_call: Execute a tool via Capability System
    - subagent_call: Delegate to a subagent
    - memory_update: Update memory with new information
    - goal_update: Update goal status or properties
    - finish_goal: Mark goal as completed

    The kernel may internally perform multi-step reasoning (e.g., ReAct-style)
    but exposes a single step interface to the Cognitive Loop.
    """

    def __init__(self, agent: NoeAgent) -> None:
        """Initialize Agent Kernel with a NoeAgent instance.

        Args:
            agent: The NoeAgent instance to wrap
        """
        self._agent = agent
        logger.info(f"AgentKernel initialized with agent {agent._agent_id}")

    async def step(self, goal: Goal, context: dict[str, Any]) -> Decision:
        """Execute one reasoning step and produce a decision.

        This method:
        1. Formulates reasoning prompt from goal + memory context
        2. Invokes agent's decision-making
        3. Parses response into Decision object
        4. Validates against available capabilities

        Args:
            goal: The goal to reason about
            context: Memory context projected for this goal

        Returns:
            Decision object with action to take

        Example:
            decision = await kernel.step(goal, context)
            if decision.action == DecisionAction.TOOL_CALL:
                # Execute tool
                result = await capability_registry.resolve(decision.tool_id)
            elif decision.action == DecisionAction.FINISH_GOAL:
                # Goal is complete
                await goal_engine.complete_goal(goal.id)
        """
        try:
            # TODO: Implement full reasoning logic
            # For now, return a placeholder decision
            # This will be enhanced to integrate with NoeAgent's planning and execution

            logger.debug(f"AgentKernel reasoning for goal: {goal.description}")

            # Formulate reasoning prompt
            reasoning_prompt = self._formulate_prompt(goal, context)

            # For now, return a thinking decision
            # Future implementation will invoke agent's LLM for actual reasoning
            decision = Decision(
                action=DecisionAction.FINISH_GOAL,
                goal_id=goal.id,
                reasoning=f"Placeholder: Goal '{goal.description}' marked as complete",
                context={"prompt": reasoning_prompt},
            )

            logger.info(f"AgentKernel decision: {decision.action} for goal {goal.id[:8]}")
            return decision

        except Exception as e:
            logger.error(f"AgentKernel step failed: {e}", exc_info=True)
            # Return a goal update decision on error
            return Decision(
                action=DecisionAction.GOAL_UPDATE,
                goal_id=goal.id,
                reasoning=f"AgentKernel error: {e}",
                new_goal_status="failed",
                goal_error=str(e),
            )

    def _formulate_prompt(self, goal: Goal, context: dict[str, Any]) -> str:
        """Formulate reasoning prompt from goal and context.

        Args:
            goal: Goal to reason about
            context: Memory context

        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            f"Goal: {goal.description}",
            f"Priority: {goal.priority}",
            f"Status: {goal.status}",
        ]

        # Add memory context
        if "related_memories" in context:
            memories = context["related_memories"]
            if memories:
                prompt_parts.append("\nRelated Memories:")
                for mem in memories[:5]:
                    prompt_parts.append(f"  - {mem.get('key', 'unknown')}: {mem.get('value', 'N/A')}")

        if "previous_execution" in context and context["previous_execution"]:
            prompt_parts.append(f"\nPrevious Execution: {context['previous_execution']}")

        return "\n".join(prompt_parts)

    @property
    def agent(self) -> NoeAgent:
        """Get the wrapped NoeAgent instance."""
        return self._agent
