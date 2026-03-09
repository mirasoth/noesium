"""Decision schema for Agent Kernel decisions (RFC-1005 Section 8).

Defines the standard decision format returned by the Agent Kernel's
reasoning step in the Cognitive Loop.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DecisionAction(str, Enum):
    """Decision action types (RFC-1005 Section 8, RFC-1006 Section 7.4).

    The Agent Kernel can produce these types of decisions:
    - tool_call: Execute a tool via Capability System
    - subagent_call: Delegate to a subagent
    - memory_update: Update memory with new information
    - create_goal: Create a new sub-goal or independent goal (RFC-1006 §7.4)
    - goal_update: Update goal status or properties
    - finish_goal: Mark goal as completed
    """

    TOOL_CALL = "tool_call"
    SUBAGENT_CALL = "subagent_call"
    MEMORY_UPDATE = "memory_update"
    CREATE_GOAL = "create_goal"
    GOAL_UPDATE = "goal_update"
    FINISH_GOAL = "finish_goal"


class Decision(BaseModel):
    """Agent Kernel decision format (RFC-1005 Section 8).

    Represents a decision produced by the Agent Kernel's reasoning step.
    The Cognitive Loop executes these decisions and returns observations.
    """

    action: DecisionAction = Field(description="Type of action to execute")
    goal_id: str = Field(description="Goal ID this decision relates to")
    reasoning: str | None = Field(
        default=None, description="Reasoning behind this decision"
    )

    # Tool execution parameters
    tool_id: str | None = Field(
        default=None, description="Tool capability ID to execute"
    )
    tool_input: dict[str, Any] = Field(
        default_factory=dict, description="Input parameters for tool"
    )

    # Subagent delegation parameters
    subagent_type: str | None = Field(
        default=None, description="Type of subagent to invoke"
    )
    subagent_task: str | None = Field(
        default=None, description="Task description for subagent"
    )

    # Memory update parameters
    memory_key: str | None = Field(default=None, description="Memory key to update")
    memory_value: Any = Field(default=None, description="Value to store in memory")
    memory_content_type: str = Field(
        default="fact", description="Content type for memory entry"
    )

    # Goal update parameters
    new_goal_status: str | None = Field(
        default=None, description="New status for goal update"
    )
    goal_error: str | None = Field(
        default=None, description="Error message if goal failed"
    )

    # Context and metadata
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Decision metadata"
    )

    model_config = ConfigDict(use_enum_values=True)


class ToolCallDecision(Decision):
    """Tool execution decision."""

    action: DecisionAction = DecisionAction.TOOL_CALL
    tool_id: str
    tool_input: dict[str, Any] = Field(default_factory=dict)


class SubagentCallDecision(Decision):
    """Subagent delegation decision."""

    action: DecisionAction = DecisionAction.SUBAGENT_CALL
    subagent_type: str
    subagent_task: str


class MemoryUpdateDecision(Decision):
    """Memory update decision."""

    action: DecisionAction = DecisionAction.MEMORY_UPDATE
    memory_key: str
    memory_value: Any
    memory_content_type: str = "fact"


class GoalUpdateDecision(Decision):
    """Goal update decision."""

    action: DecisionAction = DecisionAction.GOAL_UPDATE
    new_goal_status: str
    goal_error: str | None = None


class FinishGoalDecision(Decision):
    """Finish goal decision."""

    action: DecisionAction = DecisionAction.FINISH_GOAL


class CreateGoalDecision(Decision):
    """Create new goal decision (RFC-1006 Section 7.4).

    Enables hierarchical planning where the kernel can spawn
    new objectives during reasoning. Supports both sub-goals
    (with parent_goal_id) and independent goals.

    Example:
        # Create sub-goal for hierarchical planning
        CreateGoalDecision(
            action=DecisionAction.CREATE_GOAL,
            goal_id=current_goal.id,
            goal_description="Search arxiv for recent papers",
            goal_priority=60,
            parent_goal_id=current_goal.id,  # Link to parent
            reasoning="Need to gather sources before analysis"
        )
    """

    action: DecisionAction = DecisionAction.CREATE_GOAL
    goal_description: str = Field(description="Description of the new goal to create")
    goal_priority: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Priority for the new goal (0-100, higher = more important)",
    )
    parent_goal_id: str | None = Field(
        default=None,
        description="Parent goal ID if this is a sub-goal (for hierarchical planning)",
    )
