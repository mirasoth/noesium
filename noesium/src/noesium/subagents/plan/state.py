"""State definitions for PlanAgent.

Defines the state model with unified context handling for domain-agnostic planning.
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict


class PlanState(TypedDict):
    """State for planning workflow with unified context handling.

    Attributes:
        messages: Conversation messages (LangChain format)
        context: Provided or gathered context (unified handling)
        context_sufficient: Whether context is sufficient for planning
        explored_resources: Resources explored during context gathering
        requirements: Structured requirements extracted from objective
        constraints: Constraints that limit the plan
        plan_type: Type of plan being generated
        plan_steps: Generated plan steps
        dependencies: Dependencies between steps
        verification_steps: Verification criteria for steps
        tool_results: Results from tool executions
        clarification_questions: Questions for user clarification
        final_plan: The final structured plan output
    """

    # Messages
    messages: List[Any]

    # Context (unified handling)
    context: Dict[str, Any]
    context_sufficient: bool
    explored_resources: List[str]

    # Planning
    requirements: List[Dict[str, Any]]
    constraints: List[Dict[str, Any]]
    plan_type: Literal["implementation", "research", "workflow", "project", "general"]

    # Output
    plan_steps: List[Dict[str, Any]]
    dependencies: List[Dict[str, Any]]
    verification_steps: List[Dict[str, Any]]

    # Tool execution
    tool_results: List[Dict[str, Any]]
    file_contents: Dict[str, str]

    # Clarification
    clarification_questions: List[str]

    # Final output
    final_plan: Optional[str]
