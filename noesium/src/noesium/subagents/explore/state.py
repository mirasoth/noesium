"""State definitions for ExploreAgent."""

from typing import Any, TypedDict


class ExploreState(TypedDict):
    """State for exploration workflow.

    Attributes:
        messages: Conversation messages
        context: Additional context for exploration
        target: What to explore
        findings: List of findings
        sources: List of sources found
        tool_results: Tool execution results
        exploration_depth: Current exploration depth
        max_exploration_depth: Maximum exploration depth
        summary: Summary of findings
    """

    messages: list[Any]
    context: dict[str, Any]
    target: str
    findings: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    exploration_depth: int
    max_exploration_depth: int
    summary: str | None
