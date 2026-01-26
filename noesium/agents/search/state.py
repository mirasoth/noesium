from typing import TypedDict

try:
    from langgraph.graph import add_messages

    LANGGRAPH_AVAILABLE = True
except ImportError:
    add_messages = None
    LANGGRAPH_AVAILABLE = False

from typing_extensions import Annotated

try:
    from wizsearch import SearchResult

    WIZSEARCH_AVAILABLE = True
except ImportError:
    SearchResult = None
    WIZSEARCH_AVAILABLE = False


class SearchState(TypedDict):
    """Main state for the research workflow."""

    search_query: str
    raw_query: str
    search_results: SearchResult
    messages: Annotated[list, add_messages]
