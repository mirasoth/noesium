import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional, Type

if TYPE_CHECKING:
    from .subagent import SubagentProtocol

try:
    from langchain_core.runnables import RunnableConfig
    from langgraph.graph import StateGraph

    LANGCHAIN_AVAILABLE = True
except ImportError:
    RunnableConfig = None
    StateGraph = None
    LANGCHAIN_AVAILABLE = False

from noesium.core.llm import get_llm_client
from noesium.core.tracing import get_token_tracker
from noesium.core.utils.logging import get_logger


class BaseAgent(ABC):
    """Base class for all agents with common functionality.

    Provides:
    - LLM client management with instructor support
    - Token usage tracking
    - Capability declaration for the unified registry (RFC-1003 / RFC-2003)
    - Logging capabilities
    - Configuration management
    - Error handling patterns
    """

    def __init__(self, llm_provider: str = "openai", model_name: Optional[str] = None):
        self.logger = get_logger(self.__class__.__name__)
        self.llm_provider = llm_provider
        self.model_name = model_name
        self.llm = get_llm_client(provider=llm_provider, chat_model=model_name)
        self.logger.info(f"Initialized {self.__class__.__name__} with {llm_provider} provider")

    @abstractmethod
    async def run(
        self,
        user_message: str,
        context: Dict[str, Any] = None,
        config: Optional[RunnableConfig] = None,
    ) -> Any:
        """Run the agent with a user message and context."""

    def declare_capabilities(self) -> list:
        """Declare capabilities this agent provides (RFC-1003 §12).

        Returns a list of ``CapabilityDescriptor`` instances.  Override in
        subclasses to register the agent's capabilities with the
        ``CapabilityRegistry``.  The default implementation returns an empty
        list (agent does not self-declare any capabilities).
        """
        return []

    def get_token_usage_stats(self) -> Dict[str, Any]:
        """Get comprehensive token usage statistics."""
        return get_token_tracker().get_stats()

    def print_token_usage_summary(self):
        stats = self.get_token_usage_stats()
        if stats["total_tokens"] > 0:
            print(
                f"FINAL_SUMMARY: {stats['total_tokens']} total | {stats['total_calls']} calls | P:{stats['total_prompt_tokens']} C:{stats['total_completion_tokens']}"
            )
        else:
            print("FINAL_SUMMARY: 0 total | 0 calls | P:0 C:0")

    def as_subagent_protocol(self) -> Optional["SubagentProtocol"]:
        """Return a SubagentProtocol adapter for this agent if supported.

        Override in subclasses that can be used as subagents. Returns None
        by default, indicating the agent does not support the subagent protocol.

        Returns:
            A SubagentProtocol implementation wrapping this agent, or None.
        """
        return None


class BaseGraphicAgent(BaseAgent):
    """
    Base class for agents using LangGraph.

    Provides:
    - LangGraph state management
    - Graph building abstractions
    - Graph export functionality
    - Common graph patterns
    """

    def __init__(self, llm_provider: str = "openai", model_name: Optional[str] = None):
        """Initialize graphic agent with graph support."""
        super().__init__(llm_provider, model_name)
        self.graph: Optional[StateGraph] = None

    @abstractmethod
    def get_state_class(self) -> Type:
        """Get the state class for this agent's graph."""

    @abstractmethod
    def _build_graph(self) -> StateGraph:
        """Build the agent's graph. Must be implemented by subclasses."""

    def export_graph(self, output_path: Optional[str] = None, format: str = "png"):
        """
        Export the agent graph visualization to file.

        Args:
            output_path: Optional path for output file. If None, uses default naming.
            format: Export format ('png' or 'mermaid')
        """
        if not self.graph:
            self.logger.warning("No graph to export. Build graph first.")
            return

        if not output_path:
            class_name = self.__class__.__name__.lower()
            output_path = os.path.join(os.path.dirname(__file__), f"{class_name}_graph.{format}")

        try:
            graph_structure = self.graph.get_graph()

            if format == "png":
                try:
                    graph_structure.draw_png(output_path)
                    self.logger.info(f"Graph exported successfully to {output_path}")
                except ImportError:
                    self.logger.warning("pygraphviz not installed, trying mermaid fallback")
                    graph_structure.draw_mermaid_png(output_path)
                    self.logger.info(f"Graph exported with mermaid to {output_path}")
            elif format == "mermaid":
                # For mermaid, we might want to save the mermaid code itself
                mermaid_code = graph_structure.draw_mermaid()
                with open(output_path.replace(".png", ".md"), "w") as f:
                    f.write(f"```mermaid\n{mermaid_code}\n```")
                self.logger.info(f"Mermaid graph exported to {output_path.replace('.png', '.md')}")
            else:
                self.logger.error(f"Unsupported export format: {format}")

        except Exception as e:
            self.logger.error(f"Failed to export graph: {e}")

    def _create_error_response(self, error_message: str, **kwargs) -> Dict[str, Any]:
        """Create a standardized error response."""
        self.logger.error(f"Agent error: {error_message}")
        return {
            "error": error_message,
            "success": False,
            "timestamp": self._now_iso(),
            **kwargs,
        }

    def _now_iso(self) -> str:
        """Get current time in ISO format."""
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()
