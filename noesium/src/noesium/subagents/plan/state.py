"""State definitions for PlanAgent."""

from typing import Any, TypedDict


class PlanState(TypedDict):
    """State for planning workflow.

    Attributes:
        messages: Conversation messages
        context: Additional context for planning
        files_read: List of files that have been read
        file_contents: Actual file contents from tool execution
        tool_results: Tool execution results
        plan_steps: Current plan steps
        current_step_index: Index of current step being processed
        clarification_questions: Questions for user clarification
        final_plan: The final plan text
    """

    messages: list[Any]
    context: dict[str, Any]
    files_read: list[str]
    file_contents: dict[str, str]
    tool_results: list[dict[str, Any]]
    plan_steps: list[dict[str, Any]]
    current_step_index: int
    clarification_questions: list[str]
    final_plan: str | None