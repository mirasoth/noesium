"""Agent Kernel component (RFC-1005 Section 8).

The Agent Kernel is the reasoning engine that produces executable decisions.
It wraps a NoeAgent instance and exposes a clean step-based interface for
the Cognitive Loop to invoke.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage
from noeagent.autonomous import Goal
from noeagent.autonomous.decision_schema import (
    Decision,
    DecisionAction,
)
from noeagent.graph.nodes import _build_tool_descriptions, execute_step_node
from noeagent.state import AgentState, TaskPlan

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
        self._tool_desc_cache: str | None = None
        self._tool_desc_provider_count: int = -1
        logger.info(f"AgentKernel initialized with agent {agent._agent_id}")

    async def step(self, goal: Goal, context: dict[str, Any]) -> Decision:
        """Execute one reasoning step and produce a decision.

        This method wraps execute_step_node to perform reasoning:
        1. Creates minimal AgentState from goal and context
        2. Builds tool description cache
        3. Calls execute_step_node with proper parameters
        4. Converts AgentAction to Decision schema

        Args:
            goal: The goal to reason about
            context: Memory context projected for this goal

        Returns:
            Decision object with action to take
        """
        try:
            logger.debug(f"AgentKernel reasoning for goal: {goal.description}")

            # 1. Create minimal AgentState from goal and context
            state = self._create_agent_state(goal, context)

            # 2. Get tool description cache
            tool_desc_cache = self._get_tool_descriptions()

            # 3. Get required components from agent
            llm = self._agent.llm
            registry = self._agent.capability_registry
            memory_manager = self._agent.memory_manager

            if registry is None:
                logger.warning("No capability registry available")
                return Decision(
                    action=DecisionAction.GOAL_UPDATE,
                    goal_id=goal.id,
                    reasoning="No capability registry available",
                    new_goal_status="blocked",
                    goal_error="Capability registry not initialized",
                )

            # 4. Call execute_step_node
            result = await execute_step_node(
                state,
                llm=llm,
                registry=registry,
                memory_manager=memory_manager,
                max_tool_calls=5,
                tool_desc_cache=tool_desc_cache,
            )

            # 5. Extract AgentAction from result and convert to Decision
            decision = self._convert_to_decision(goal, result)

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

    def _create_agent_state(self, goal: Goal, context: dict[str, Any]) -> AgentState:
        """Create minimal AgentState from goal and context.

        Args:
            goal: The goal to create state for
            context: Memory context with previous execution info

        Returns:
            AgentState TypedDict suitable for execute_step_node
        """
        # Create a simple plan from the goal
        plan = TaskPlan(
            goal=goal.description,
            steps=[],
            current_step_index=0,
            is_complete=False,
        )

        # Build messages from context
        messages: list[Any] = []

        # Add the goal as the user message
        goal_message = HumanMessage(content=goal.description)
        messages.append(goal_message)

        # Add previous execution context if available
        previous_exec = context.get("previous_execution")
        if previous_exec:
            # Include previous execution results as context
            from langchain_core.messages import SystemMessage

            exec_context = SystemMessage(content=f"Previous execution: {previous_exec}")
            messages.append(exec_context)

        # Extract tool results from context
        tool_results: list[dict[str, Any]] = []
        related_memories = context.get("related_memories", [])
        if related_memories:
            for mem in related_memories[:5]:
                tool_results.append(
                    {
                        "tool": mem.get("key", "memory"),
                        "result": mem.get("value", ""),
                    }
                )

        return AgentState(
            messages=messages,
            plan=plan,
            iteration=0,
            tool_results=tool_results,
            reflection="",
            final_answer="",
        )

    def _get_tool_descriptions(self) -> str:
        """Build and cache tool descriptions from capability registry.

        Returns:
            Formatted tool descriptions string
        """
        registry = self._agent.capability_registry
        if registry is None:
            return "No tools available."

        # Check if cache is still valid
        provider_count = len(registry.list_providers())
        if self._tool_desc_cache is not None and self._tool_desc_provider_count == provider_count:
            return self._tool_desc_cache

        # Build new cache
        self._tool_desc_cache = _build_tool_descriptions(registry)
        self._tool_desc_provider_count = provider_count
        return self._tool_desc_cache

    def _convert_to_decision(self, goal: Goal, result: dict[str, Any]) -> Decision:
        """Convert execute_step_node result to Decision schema.

        Args:
            goal: The goal being processed
            result: Result dict from execute_step_node containing messages

        Returns:
            Decision object with appropriate action type
        """
        from langchain_core.messages import AIMessage

        messages = result.get("messages", [])
        if not messages:
            return Decision(
                action=DecisionAction.FINISH_GOAL,
                goal_id=goal.id,
                reasoning="No action produced, marking goal complete",
            )

        last_message = messages[-1]

        # Handle AIMessage with tool calls
        if isinstance(last_message, AIMessage):
            tool_calls = getattr(last_message, "tool_calls", None)
            additional_kwargs = getattr(last_message, "additional_kwargs", {})
            content = last_message.content or ""

            # Check for tool calls
            if tool_calls:
                # Use first tool call as the primary action
                first_call = tool_calls[0]
                return Decision(
                    action=DecisionAction.TOOL_CALL,
                    goal_id=goal.id,
                    reasoning=content,
                    tool_id=first_call.get("name", ""),
                    tool_input=first_call.get("args", {}),
                )

            # Check for subagent action
            if "subagent_action" in additional_kwargs:
                subagent_data = additional_kwargs["subagent_action"]
                return Decision(
                    action=DecisionAction.SUBAGENT_CALL,
                    goal_id=goal.id,
                    reasoning=content,
                    subagent_type=subagent_data.get("name", "unknown"),
                    subagent_task=subagent_data.get("message", ""),
                )

            # Text response - check if it indicates completion
            # If no tools or subagents, treat as a step toward completion
            if content:
                # Check if this appears to be a final answer
                completion_indicators = [
                    "task is complete",
                    "goal accomplished",
                    "finished",
                    "done",
                    "here is the answer",
                    "the answer is",
                    "in summary",
                ]
                content_lower = content.lower()
                is_completion = any(indicator in content_lower for indicator in completion_indicators)

                if is_completion:
                    return Decision(
                        action=DecisionAction.FINISH_GOAL,
                        goal_id=goal.id,
                        reasoning=content,
                    )

                # Otherwise, this is a thinking step that should continue
                return Decision(
                    action=DecisionAction.MEMORY_UPDATE,
                    goal_id=goal.id,
                    reasoning=content,
                    memory_key=f"step_result:{goal.id[:8]}",
                    memory_value=content,
                    memory_content_type="execution_trace",
                )

        # Fallback: treat as completion
        return Decision(
            action=DecisionAction.FINISH_GOAL,
            goal_id=goal.id,
            reasoning=(str(last_message.content) if hasattr(last_message, "content") else "Step completed"),
        )

    @property
    def agent(self) -> NoeAgent:
        """Get the wrapped NoeAgent instance."""
        return self._agent
