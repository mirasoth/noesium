"""Decoupled Agent Kernel for autonomous mode (RFC-1005 §8).

This module provides a dedicated AgentKernel that doesn't depend on
the interactive mode's LangGraph nodes, using instructor for structured
decision parsing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

try:
    import instructor
except ImportError:
    instructor = None

from noeagent.autonomous.decision_schema import (
    CreateGoalDecision,
    Decision,
    DecisionAction,
)
from noeagent.autonomous.goal_engine import Goal
from noeagent.autonomous.kernel.reasoning_chain import AutonomousReasoningChain

if TYPE_CHECKING:
    from noeagent.agent import NoeAgent

logger = logging.getLogger(__name__)


class AgentKernel:
    """Reasoning engine that produces executable decisions (RFC-1005 §8).

    UPDATED: Uses dedicated AutonomousReasoningChain instead of
    interactive mode's execute_step_node, eliminating cross-mode dependency.

    Uses instructor for structured output parsing to ensure decisions
    are properly typed and validated.

    The kernel exposes a simple step-based interface:
        step(goal, context) -> Decision

    Each step produces a decision that the Cognitive Loop executes.
    Decision types:
    - tool_call: Execute tool via Capability System
    - subagent_call: Delegate to subagent
    - memory_update: Update memory with new information
    - create_goal: Create new sub-goal (RFC-1006 §7.4)
    - goal_update: Update goal status
    - finish_goal: Mark goal completed

    The kernel performs reasoning without depending on interactive graph.
    """

    def __init__(self, agent: NoeAgent) -> None:
        """Initialize Agent Kernel with NoeAgent instance.

        Args:
            agent: NoeAgent instance providing LLM and capabilities
        """
        self._agent = agent
        self._reasoning_chain: AutonomousReasoningChain | None = None
        self._tool_desc_cache: str | None = None
        self._instructor_llm: Any = None

        logger.info("AgentKernel initialized for autonomous mode (decoupled)")

    def _get_instructor_llm(self) -> Any:
        """Get instructor-wrapped LLM for structured output.

        Returns:
            Instructor-wrapped LLM client
        """
        if self._instructor_llm is not None:
            return self._instructor_llm

        if instructor is None:
            logger.warning(
                "instructor not installed. Falling back to unstructured parsing. "
                "Install with: uv run pip install instructor"
            )
            return self._agent.llm

        try:
            # Wrap LLM with instructor for structured output
            self._instructor_llm = instructor.from_langchain(self._agent.llm)
            logger.debug("Instructor-wrapped LLM initialized")
            return self._instructor_llm
        except Exception as e:
            logger.warning(f"Failed to wrap LLM with instructor: {e}. Using fallback.")
            return self._agent.llm

    async def step(self, goal: Goal, context: dict[str, Any]) -> Decision:
        """Execute one reasoning step and produce a decision.

        Uses AutonomousReasoningChain for dedicated autonomous reasoning
        and instructor for structured decision parsing.

        Args:
            goal: Goal to reason about
            context: Memory context from MemoryProjector

        Returns:
            Decision object with action to take
        """
        try:
            logger.debug(f"AgentKernel reasoning for goal: {goal.description}")

            # Initialize reasoning chain if needed (lazy)
            if self._reasoning_chain is None:
                tool_desc = self._get_tool_descriptions()
                llm = self._get_instructor_llm()
                self._reasoning_chain = AutonomousReasoningChain(
                    llm=llm,
                    tool_descriptions=tool_desc,
                )

            # Execute autonomous reasoning
            response = await self._reasoning_chain.reason(goal, context)

            # Parse response into typed Decision
            decision = await self._parse_response_to_decision(goal, response)

            logger.info(
                f"AgentKernel decision: {decision.action} for goal {goal.id[:8]}"
            )
            return decision

        except Exception as e:
            logger.error(f"AgentKernel step failed: {e}", exc_info=True)
            # Return error decision
            return Decision(
                action=DecisionAction.GOAL_UPDATE,
                goal_id=goal.id,
                reasoning=f"AgentKernel error: {e}",
                new_goal_status="failed",
                goal_error=str(e),
            )

    async def _parse_response_to_decision(self, goal: Goal, response: Any) -> Decision:
        """Parse LLM response into typed Decision using instructor.

        If instructor is available and response is structured, extract
        decision directly. Otherwise, use heuristic parsing.

        Args:
            goal: Goal being processed
            response: LLM response object

        Returns:
            Typed Decision object
        """
        content = response.content if hasattr(response, "content") else str(response)

        # Try structured extraction if instructor was used
        if hasattr(response, "model_dump"):
            # Structured output from instructor
            try:
                data = response.model_dump()
                action_str = data.get("action", "finish_goal")

                # Map string to DecisionAction
                action_map = {
                    "tool_call": DecisionAction.TOOL_CALL,
                    "subagent_call": DecisionAction.SUBAGENT_CALL,
                    "memory_update": DecisionAction.MEMORY_UPDATE,
                    "create_goal": DecisionAction.CREATE_GOAL,
                    "goal_update": DecisionAction.GOAL_UPDATE,
                    "finish_goal": DecisionAction.FINISH_GOAL,
                }

                action = action_map.get(action_str, DecisionAction.FINISH_GOAL)

                # Build appropriate decision type
                if action == DecisionAction.CREATE_GOAL:
                    return CreateGoalDecision(
                        action=action,
                        goal_id=goal.id,
                        goal_description=data.get("goal_description", "New sub-goal"),
                        goal_priority=data.get("goal_priority", 60),
                        parent_goal_id=data.get("parent_goal_id", goal.id),
                        reasoning=content,
                    )
                else:
                    return Decision(
                        action=action,
                        goal_id=goal.id,
                        reasoning=content,
                        tool_id=data.get("tool_id"),
                        tool_input=data.get("tool_input", {}),
                        subagent_type=data.get("subagent_type"),
                        subagent_task=data.get("subagent_task"),
                        memory_key=data.get("memory_key"),
                        memory_value=data.get("memory_value"),
                        new_goal_status=data.get("new_goal_status"),
                    )
            except Exception as e:
                logger.debug(f"Structured extraction failed: {e}, using heuristics")

        # Fallback: heuristic parsing
        return self._heuristic_parse(goal, content)

    def _heuristic_parse(self, goal: Goal, content: str) -> Decision:
        """Parse decision using heuristics when structured output unavailable.

        Args:
            goal: Goal being processed
            content: Response content string

        Returns:
            Decision object
        """
        import re

        content_lower = content.lower()

        # Detect goal creation intent
        create_indicators = [
            "create_goal",
            "new goal",
            "sub-goal",
            "subgoal",
            "spawn goal",
            "break down into",
            "split into tasks",
        ]

        if any(ind in content_lower for ind in create_indicators):
            goal_desc = self._extract_new_goal_description(content)
            priority = self._extract_priority(content) or 60

            logger.debug(f"Detected create_goal decision: {goal_desc}")
            return CreateGoalDecision(
                action=DecisionAction.CREATE_GOAL,
                goal_id=goal.id,
                goal_description=goal_desc,
                goal_priority=priority,
                parent_goal_id=goal.id,
                reasoning=content,
            )

        # Detect finish intent
        finish_indicators = [
            "finish_goal",
            "goal complete",
            "task finished",
            "done",
            "completed",
            "accomplished",
        ]

        if any(ind in content_lower for ind in finish_indicators):
            logger.debug("Detected finish_goal decision")
            return Decision(
                action=DecisionAction.FINISH_GOAL,
                goal_id=goal.id,
                reasoning=content,
            )

        # Detect tool call
        tool_pattern = r"(?:use|call|execute)\s+(?:tool\s+)?(\w+)"
        tool_match = re.search(tool_pattern, content_lower)

        if tool_match:
            tool_name = tool_match.group(1)
            logger.debug(f"Detected tool_call decision: {tool_name}")
            return Decision(
                action=DecisionAction.TOOL_CALL,
                goal_id=goal.id,
                reasoning=content,
                tool_id=tool_name,
                tool_input={},
            )

        # Default: memory update
        return Decision(
            action=DecisionAction.MEMORY_UPDATE,
            goal_id=goal.id,
            reasoning=content,
            memory_key=f"step:{goal.id[:8]}",
            memory_value=content,
            memory_content_type="execution_trace",
        )

    def _extract_new_goal_description(self, content: str) -> str:
        """Extract new goal description from reasoning content."""
        lines = content.split("\n")
        for line in lines:
            if "new goal" in line.lower() or "sub-goal" in line.lower():
                if ":" in line:
                    return line.split(":", 1)[1].strip()
        return "New sub-goal"

    def _extract_priority(self, content: str) -> int | None:
        """Extract priority from content if mentioned."""
        import re

        match = re.search(r"priority[:\s]+(\d+)", content.lower())
        if match:
            return int(match.group(1))
        return None

    def _get_tool_descriptions(self) -> str:
        """Get tool descriptions from capability registry.

        Returns:
            Formatted tool descriptions string
        """
        if self._tool_desc_cache is not None:
            return self._tool_desc_cache

        registry = self._agent.capability_registry
        if registry is None:
            return "No tools available."

        # Reuse existing tool description builder
        from noeagent.graph.nodes import _build_tool_descriptions

        self._tool_desc_cache = _build_tool_descriptions(registry)

        return self._tool_desc_cache

    @property
    def agent(self) -> NoeAgent:
        """Get wrapped NoeAgent instance."""
        return self._agent
