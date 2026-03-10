"""ExploreAgent implementation for gathering information."""

from typing import Any, AsyncGenerator, Dict, List, Optional, Type

try:
    from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
    from langchain_core.runnables import RunnableConfig
    from langgraph.graph import END, START, StateGraph

    LANGCHAIN_AVAILABLE = True
except ImportError:
    AIMessage = None
    AnyMessage = None
    HumanMessage = None
    RunnableConfig = None
    StateGraph = None
    END = None
    START = None
    LANGCHAIN_AVAILABLE = False

from uuid_extensions import uuid7str

from noesium.core.agent import BaseGraphicAgent
from noesium.core.utils.logging import get_logger
from noesium.core.utils.typing import override
from noesium.toolkits import (
    TOOLKIT_AUDIO,
    TOOLKIT_BASH,
    TOOLKIT_DOCUMENT,
    TOOLKIT_FILE_EDIT,
    TOOLKIT_IMAGE,
    TOOLKIT_PYTHON_EXECUTOR,
    TOOLKIT_TABULAR_DATA,
    TOOLKIT_VIDEO,
)
from noesium.utils.tool_utils import ToolHelper, create_tool_helper

from .prompts import (
    EXPLORE_SYSTEM_PROMPT,
    SYNTHESIS_PROMPT,
    TARGET_ANALYSIS_PROMPT,
)
from .state import ExploreState

logger = get_logger(__name__)


class ExploreAgent(BaseGraphicAgent):
    """Exploration agent for gathering information from codebases and data.

    This agent:
    1. Analyzes exploration targets
    2. Uses comprehensive read-only toolkits
    3. Gathers information systematically
    4. Tracks findings and sources
    5. Synthesizes results into clear summaries
    """

    def __init__(
        self,
        llm_provider: str = "openai",
        max_exploration_depth: int = 3,
        exploration_temperature: float = 0.5,
        exploration_max_tokens: int = 4000,
        agent_id: str | None = None,
        working_directory: str | None = None,
    ):
        """Initialize ExploreAgent.

        Args:
            llm_provider: LLM provider to use
            max_exploration_depth: Maximum exploration depth
            exploration_temperature: Temperature for exploration
            exploration_max_tokens: Max tokens for exploration
            agent_id: Optional agent ID (auto-generated if None)
            working_directory: Working directory for file operations
        """
        super().__init__(llm_provider=llm_provider)

        self.max_exploration_depth = max_exploration_depth
        self.exploration_temperature = exploration_temperature
        self.exploration_max_tokens = exploration_max_tokens

        # Generate agent ID
        self.agent_id = agent_id or f"explore-{uuid7str()[:8]}"

        # Tool configuration - comprehensive read-only
        self.enabled_toolkits = [
            TOOLKIT_FILE_EDIT,
            TOOLKIT_BASH,
            TOOLKIT_PYTHON_EXECUTOR,
            TOOLKIT_DOCUMENT,
            TOOLKIT_AUDIO,
            TOOLKIT_IMAGE,
            TOOLKIT_VIDEO,
            TOOLKIT_TABULAR_DATA,
        ]
        self.permissions = ["fs:read", "env:read", "shell:execute"]  # Read-only!

        self._tool_helper: ToolHelper | None = None
        self._working_directory = working_directory

        # Build the exploration graph
        self.graph = self._build_graph()

    @override
    def get_state_class(self) -> Type:
        """Get the state class for this agent."""
        return ExploreState

    async def _ensure_tool_helper(self) -> ToolHelper:
        """Lazily initialize tool helper."""
        if self._tool_helper is None:
            # Configure toolkit restrictions
            toolkit_configs = {
                "bash": {
                    "readonly": True,
                    "allowed_commands": ["ls", "cat", "head", "tail", "grep", "find"],
                },
                "python_executor": {"readonly": True},
                "document": {"readonly": True},
                "audio": {"activated_tools": ["transcribe_audio", "get_audio_info"]},
                "image": {"readonly": True},
                "video": {"readonly": True},
                "tabular_data": {"readonly": True},
            }

            self._tool_helper = await create_tool_helper(
                agent_id=self.agent_id,
                enabled_toolkits=self.enabled_toolkits,
                permissions=self.permissions,
                working_directory=self._working_directory,
                toolkit_configs=toolkit_configs,
            )
        return self._tool_helper

    @override
    def _build_graph(self) -> StateGraph:
        """Build the exploration workflow graph."""
        workflow = StateGraph(ExploreState)

        # Add nodes
        workflow.add_node("analyze_target", self._analyze_target_node)
        workflow.add_node("explore_sources", self._explore_sources_node)
        workflow.add_node("synthesize", self._synthesize_node)

        # Set entry point
        workflow.add_edge(START, "analyze_target")

        # Add edges
        workflow.add_edge("analyze_target", "explore_sources")
        workflow.add_edge("explore_sources", "synthesize")
        workflow.add_edge("synthesize", END)

        return workflow.compile()

    async def _analyze_target_node(self, state: ExploreState, config: RunnableConfig) -> Dict[str, Any]:
        """Analyze the exploration target and determine approach."""
        target = state.get("target", "")

        prompt = TARGET_ANALYSIS_PROMPT.format(
            target=target,
            context=state.get("context", {}),
        )

        response = self.llm.completion(
            messages=[
                {"role": "system", "content": EXPLORE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self.exploration_temperature,
            max_tokens=self.exploration_max_tokens,
        )

        return {
            "messages": [AIMessage(content=response)],
        }

    async def _explore_sources_node(self, state: ExploreState, config: RunnableConfig) -> Dict[str, Any]:
        """Explore sources using actual tools."""
        target = state.get("target", "")
        current_depth = state.get("exploration_depth", 0)

        # Ensure tool helper is ready
        tool_helper = await self._ensure_tool_helper()

        findings = []
        sources = []
        tool_results = []

        # Strategy 1: Search for relevant files
        try:
            search_result = await tool_helper.execute_tool(
                "file_edit:search_in_files",
                query=target,
                path=".",
            )
            tool_results.append(
                {
                    "tool": "search_in_files",
                    "success": True,
                    "result": search_result,
                }
            )

            # Parse search results into findings
            for match in search_result.get("matches", [])[:10]:
                findings.append(
                    {
                        "title": f"Found in {match['file']}",
                        "description": match.get("context", ""),
                        "source": match["file"],
                        "relevance": "high",
                        "details": match,
                    }
                )
                sources.append(
                    {
                        "type": "file",
                        "name": match["file"],
                        "location": match["file"],
                        "summary": match.get("context", "")[:100],
                    }
                )
        except Exception as e:
            logger.warning(f"Search failed: {e}")
            tool_results.append(
                {
                    "tool": "search_in_files",
                    "success": False,
                    "error": str(e),
                }
            )

        # Strategy 2: List relevant files
        try:
            list_result = await tool_helper.execute_tool(
                "file_edit:list_files",
                path=".",
                pattern="**/*.py",  # Could be made dynamic based on target
            )
            tool_results.append(
                {
                    "tool": "list_files",
                    "success": True,
                    "result": list_result,
                }
            )

            for file_path in list_result.get("files", [])[:20]:
                sources.append(
                    {
                        "type": "file",
                        "name": file_path,
                        "location": file_path,
                        "summary": "Discovered during exploration",
                    }
                )
        except Exception as e:
            logger.warning(f"List files failed: {e}")

        # Strategy 3: Read key files found in search
        key_files = set()
        for finding in findings[:3]:
            if finding.get("source"):
                key_files.add(finding["source"])

        for file_path in list(key_files)[:5]:
            try:
                read_result = await tool_helper.execute_tool(
                    "file_edit:read_file",
                    file_path=file_path,
                )
                tool_results.append(
                    {
                        "tool": "read_file",
                        "file_path": file_path,
                        "success": True,
                        "size": len(read_result),
                    }
                )

                findings.append(
                    {
                        "title": f"Content of {file_path}",
                        "description": read_result[:500],
                        "source": file_path,
                        "relevance": "medium",
                        "details": {"full_content": read_result},
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")

        return {
            "findings": findings,
            "sources": sources,
            "tool_results": tool_results,
            "exploration_depth": current_depth + 1,
        }

    async def _synthesize_node(self, state: ExploreState, config: RunnableConfig) -> Dict[str, Any]:
        """Synthesize findings into a summary."""
        target = state.get("target", "")
        findings = state.get("findings", [])
        sources = state.get("sources", [])

        # Format findings and sources for prompt
        findings_text = self._format_findings(findings)
        sources_text = self._format_sources(sources)

        prompt = SYNTHESIS_PROMPT.format(
            target=target,
            findings=findings_text,
            sources=sources_text,
        )

        response = self.llm.completion(
            messages=[
                {"role": "system", "content": EXPLORE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self.exploration_temperature,
            max_tokens=self.exploration_max_tokens,
        )

        return {
            "messages": [AIMessage(content=response)],
            "summary": response,
        }

    def _extract_analysis(self, messages: List[AnyMessage]) -> str:
        """Extract analysis from messages."""
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                return message.content
        return ""

    def _format_findings(self, findings: List[Dict[str, Any]]) -> str:
        """Format findings for synthesis prompt."""
        formatted = []
        for i, finding in enumerate(findings, 1):
            formatted.append(
                f"{i}. {finding.get('title', 'Unknown')}\n"
                f"   Description: {finding.get('description', 'No description')}\n"
                f"   Source: {finding.get('source', 'Unknown')}\n"
                f"   Relevance: {finding.get('relevance', 'high')}"
            )
        return "\n\n".join(formatted) if formatted else "No findings yet"

    def _format_sources(self, sources: List[Dict[str, Any]]) -> str:
        """Format sources for synthesis prompt."""
        formatted = []
        for source in sources:
            formatted.append(
                f"- {source.get('type', 'unknown')}: {source.get('name', 'unknown')}\n"
                f"  Location: {source.get('location', 'unknown')}\n"
                f"  Summary: {source.get('summary', 'No summary')}"
            )
        return "\n".join(formatted) if formatted else "No sources tracked"

    @override
    async def run(
        self,
        user_message: str,
        context: Dict[str, Any] = None,
        config: Optional[RunnableConfig] = None,
    ) -> str:
        """Run the exploration agent and return the summary.

        Args:
            user_message: What to explore
            context: Additional context
            config: Runtime configuration

        Returns:
            The exploration summary as text
        """
        initial_state: ExploreState = {
            "messages": [HumanMessage(content=user_message)],
            "context": context or {},
            "target": user_message,
            "findings": [],
            "sources": [],
            "tool_results": [],
            "exploration_depth": 0,
            "max_exploration_depth": self.max_exploration_depth,
            "summary": None,
        }

        result = await self.graph.ainvoke(initial_state, config=config)

        return result.get("summary", "Exploration failed")

    async def astream_progress(
        self,
        user_message: str,
        context: Dict[str, Any] = None,
        config: Optional[RunnableConfig] = None,
    ) -> AsyncGenerator[Any, None]:
        """Stream progress events during exploration.

        Args:
            user_message: What to explore
            context: Additional context
            config: Runtime configuration

        Yields:
            ProgressEvent: Events describing exploration progress
        """
        from uuid_extensions import uuid7str

        from noesium.core.event import ProgressEvent, ProgressEventType

        session_id = uuid7str()

        # Yield SESSION_START
        yield ProgressEvent(
            type=ProgressEventType.SESSION_START,
            session_id=session_id,
            summary=f"Exploring: {user_message[:60]}",
        )

        # Initialize state
        initial_state: ExploreState = {
            "messages": [HumanMessage(content=user_message)],
            "context": context or {},
            "target": user_message,
            "findings": [],
            "sources": [],
            "tool_results": [],
            "exploration_depth": 0,
            "max_exploration_depth": self.max_exploration_depth,
            "summary": None,
        }

        try:
            # Yield thinking event
            yield ProgressEvent(
                type=ProgressEventType.THINKING,
                session_id=session_id,
                summary="Analyzing exploration target...",
            )

            # Stream graph execution
            total_findings = 0
            total_sources = 0

            async for event in self.graph.astream(initial_state):
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue

                    if node_name == "analyze_target":
                        yield ProgressEvent(
                            type=ProgressEventType.THINKING,
                            session_id=session_id,
                            summary="Determining exploration strategy...",
                        )

                    elif node_name == "explore_sources":
                        findings = node_output.get("findings", [])
                        sources = node_output.get("sources", [])
                        tool_results = node_output.get("tool_results", [])
                        depth = node_output.get("exploration_depth", 0)

                        total_findings = len(findings)
                        total_sources = len(sources)

                        # Yield step events for exploration
                        yield ProgressEvent(
                            type=ProgressEventType.STEP_START,
                            session_id=session_id,
                            step_index=depth - 1,
                            summary=f"Exploration depth {depth}/{self.max_exploration_depth}",
                        )

                        # Emit tool events based on actual tool execution
                        for tool_result in tool_results:
                            tool_name = tool_result.get("tool", "unknown")
                            success = tool_result.get("success", False)

                            # Emit TOOL_START
                            yield ProgressEvent(
                                type=ProgressEventType.TOOL_START,
                                session_id=session_id,
                                tool_name=tool_name,
                                summary=f"Executing {tool_name}...",
                            )

                            # Emit TOOL_END
                            if success:
                                if tool_name == "read_file":
                                    file_path = tool_result.get("file_path", "")
                                    size = tool_result.get("size", 0)
                                    yield ProgressEvent(
                                        type=ProgressEventType.TOOL_END,
                                        session_id=session_id,
                                        tool_name=tool_name,
                                        tool_result=f"Read {file_path} ({size} bytes)",
                                        summary=f"Read {file_path}",
                                    )
                                else:
                                    tool_result.get("result", {})
                                    yield ProgressEvent(
                                        type=ProgressEventType.TOOL_END,
                                        session_id=session_id,
                                        tool_name=tool_name,
                                        tool_result=f"Success: {tool_name}",
                                        summary=f"{tool_name} completed",
                                    )
                            else:
                                error = tool_result.get("error", "Unknown error")
                                yield ProgressEvent(
                                    type=ProgressEventType.TOOL_END,
                                    session_id=session_id,
                                    tool_name=tool_name,
                                    tool_result=f"Failed: {error}",
                                    summary=f"{tool_name} failed",
                                )

                        # Yield partial results
                        if findings:
                            yield ProgressEvent(
                                type=ProgressEventType.PARTIAL_RESULT,
                                session_id=session_id,
                                text=f"Found {total_findings} items so far",
                                summary=f"Found {total_findings} findings",
                            )

                    elif node_name == "synthesize":
                        summary = node_output.get("summary", "")

                        yield ProgressEvent(
                            type=ProgressEventType.THINKING,
                            session_id=session_id,
                            summary="Synthesizing findings...",
                        )

                        # Yield final answer
                        yield ProgressEvent(
                            type=ProgressEventType.FINAL_ANSWER,
                            session_id=session_id,
                            text=summary,
                            summary=f"Exploration complete ({total_findings} findings, {total_sources} sources)",
                        )

        except Exception as e:
            logger.error(f"Exploration failed: {e}")
            yield ProgressEvent(
                type=ProgressEventType.ERROR,
                session_id=session_id,
                error=str(e),
                summary=f"Exploration failed: {str(e)[:60]}",
            )
            raise

        finally:
            # Yield SESSION_END
            yield ProgressEvent(
                type=ProgressEventType.SESSION_END,
                session_id=session_id,
            )
