"""State definitions for ExploreAgent.

Defines the state model with target type classification and reflection loop support
for domain-agnostic exploration across files, documents, data, and media.
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict


class ExploreState(TypedDict):
    """State for exploration workflow with reflection loop.

    Attributes:
        messages: Conversation messages (LangChain format)
        target: What to explore (query or description)
        target_type: Classification of the target type
        context: Additional context for exploration

        search_strategy: List of search queries to execute
        findings: Accumulated findings from exploration
        sources: Sources accessed during exploration
        tool_results: Results from tool executions

        reflection: Result of reflection on exploration progress
        exploration_loops: Current exploration loop count
        max_loops: Maximum exploration loops allowed
        is_sufficient: Whether gathered info is sufficient

        summary: Final synthesized summary
        confidence_score: Confidence in the findings (0-1)
    """

    # Input
    messages: List[Any]
    target: str
    target_type: Literal["code", "document", "data", "media", "general"]
    context: Dict[str, Any]

    # Exploration
    search_strategy: List[Dict[str, Any]]
    findings: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]

    # Reflection loop
    reflection: Optional[Dict[str, Any]]
    exploration_loops: int
    max_loops: int
    is_sufficient: bool

    # Output
    summary: Optional[str]
    confidence_score: float
