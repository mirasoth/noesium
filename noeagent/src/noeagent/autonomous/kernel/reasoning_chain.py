"""Autonomous reasoning chain for Agent Kernel (RFC-1005 §8).

Provides a dedicated reasoning path for autonomous mode that doesn't
depend on the interactive mode's LangGraph nodes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.prompts import ChatPromptTemplate

if TYPE_CHECKING:
    from noeagent.autonomous.goal_engine import Goal

logger = logging.getLogger(__name__)


AUTONOMOUS_REASONING_PROMPT = """You are an autonomous agent kernel. Your role is to reason about goals and decide what actions to take to achieve them.

# Current Goal
- ID: {goal_id}
- Description: {goal_description}
- Priority: {goal_priority} (0-100, higher = more important)
- Status: {goal_status}

# Memory Context
{memory_context}

# Available Tools
{tool_descriptions}

# Your Capabilities
You can take the following actions:
1. **tool_call**: Execute a tool to gather information or perform actions
2. **subagent_call**: Delegate a task to a specialized subagent
3. **memory_update**: Store new information in memory for future reference
4. **create_goal**: Create a new sub-goal for hierarchical planning
5. **goal_update**: Update the current goal's status
6. **finish_goal**: Mark the goal as completed

# Decision Process
Think step-by-step about what action will best achieve the current goal:
1. Analyze the goal and available context
2. Determine what information or action is needed next
3. Choose the most appropriate action type
4. Provide clear reasoning for your choice

If you need to break down the goal into smaller tasks, use **create_goal** to spawn sub-goals.
If the goal is complete, use **finish_goal**.
If you need to delegate to a specialist, use **subagent_call**.
Otherwise, use **tool_call** to take action or **memory_update** to save findings.

Output your decision in a structured format indicating the action type and parameters."""


class AutonomousReasoningChain:
    """Lightweight reasoning chain for autonomous mode.

    Provides a dedicated reasoning path for the autonomous kernel
    that doesn't depend on the interactive mode's LangGraph nodes.

    This decouples the autonomous reasoning from the interactive workflow,
    allowing each mode to have optimized prompts and processing.

    Example:
        chain = AutonomousReasoningChain(llm, tool_descriptions)
        response = await chain.reason(goal, context)
        decision = parse_response(response)
    """

    def __init__(self, llm: Any, tool_descriptions: str):
        """Initialize reasoning chain.

        Args:
            llm: Language model client (with instructor support)
            tool_descriptions: Formatted tool descriptions string
        """
        self.llm = llm
        self.tool_descriptions = tool_descriptions

        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", AUTONOMOUS_REASONING_PROMPT),
                ("human", "What action should I take next to achieve the goal?"),
            ]
        )

        self.chain = self.prompt | self.llm
        logger.debug("AutonomousReasoningChain initialized")

    async def reason(self, goal: Goal, context: dict[str, Any]) -> Any:
        """Execute reasoning step for autonomous mode.

        Args:
            goal: Goal to reason about
            context: Memory context from MemoryProjector

        Returns:
            LLM response with action decision
        """
        memory_context = self._format_context(context)

        response = await self.chain.ainvoke(
            {
                "goal_id": goal.id,
                "goal_description": goal.description,
                "goal_priority": goal.priority,
                "goal_status": goal.status.value,
                "memory_context": memory_context,
                "tool_descriptions": self.tool_descriptions,
            }
        )

        logger.debug(f"Reasoning complete for goal {goal.id[:8]}")
        return response

    def _format_context(self, context: dict[str, Any]) -> str:
        """Format memory context for prompt.

        Args:
            context: Memory context dictionary

        Returns:
            Formatted string for prompt
        """
        parts = []

        if context.get("related_memories"):
            parts.append("## Related Memories")
            for mem in context["related_memories"][:3]:
                key = mem.get("key", "unknown")
                value = str(mem.get("value", ""))[:100]
                parts.append(f"  - {key}: {value}")

        if context.get("previous_execution"):
            parts.append("\n## Previous Execution")
            parts.append(f"  {context['previous_execution']}")

        if context.get("goal_history"):
            parts.append("\n## Goal History")
            parts.append(f"  {context['goal_history']}")

        return "\n".join(parts) if parts else "No relevant context available."
