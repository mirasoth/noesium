"""ExploreAgent implementation for gathering information from diverse sources.

A general-purpose exploration agent that discovers and synthesizes essential
information from files, documents, media, data, and structured content.
Features a reflection loop for iterative quality control.
"""

import json
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
    REFLECTION_PROMPT,
    STRATEGY_GENERATION_PROMPT,
    SYNTHESIS_PROMPT,
    TARGET_ANALYSIS_PROMPT,
)
from .schemas import ExploreResult, Finding, Source
from .state import ExploreState

logger = get_logger(__name__)


class ExploreAgent(BaseGraphicAgent):
    """Exploration agent for gathering information from diverse sources.

    This agent:
    1. Analyzes exploration targets and determines target type
    2. Generates multi-pronged search strategies
    3. Executes exploration using comprehensive read-only toolkits
    4. Reflects on completeness and loops if needed
    5. Synthesizes findings into structured results

    Workflow:
    START → analyze_target → generate_strategy → explore_sources →
    reflect → [loop if insufficient] → synthesize → END
    """

    def __init__(
        self,
        llm_provider: str = "openai",
        max_loops: int = 3,
        exploration_temperature: float = 0.5,
        exploration_max_tokens: int = 4000,
        agent_id: str | None = None,
        working_directory: str | None = None,
    ):
        """Initialize ExploreAgent.

        Args:
            llm_provider: LLM provider to use
            max_loops: Maximum exploration loops (reflection iterations)
            exploration_temperature: Temperature for exploration
            exploration_max_tokens: Max tokens for exploration
            agent_id: Optional agent ID (auto-generated if None)
            working_directory: Working directory for file operations
        """
        super().__init__(llm_provider=llm_provider)

        self.max_loops = max_loops
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
        """Build the exploration workflow graph with reflection loop."""
        workflow = StateGraph(ExploreState)

        # Add nodes
        workflow.add_node("analyze_target", self._analyze_target_node)
        workflow.add_node("generate_strategy", self._generate_strategy_node)
        workflow.add_node("explore_sources", self._explore_sources_node)
        workflow.add_node("reflect", self._reflect_node)
        workflow.add_node("synthesize", self._synthesize_node)

        # Set entry point
        workflow.add_edge(START, "analyze_target")

        # Linear flow to exploration
        workflow.add_edge("analyze_target", "generate_strategy")
        workflow.add_edge("generate_strategy", "explore_sources")
        workflow.add_edge("explore_sources", "reflect")

        # Conditional branching from reflect
        workflow.add_conditional_edges(
            "reflect",
            self._should_continue_exploring,
            {
                "continue": "explore_sources",
                "synthesize": "synthesize",
            },
        )

        # End after synthesis
        workflow.add_edge("synthesize", END)

        return workflow.compile()

    def _should_continue_exploring(self, state: ExploreState) -> str:
        """Determine whether to continue exploring or synthesize."""
        reflection = state.get("reflection")
        current_loop = state.get("exploration_loops", 0)
        max_loops = state.get("max_loops", self.max_loops)

        # Check if we have reflection results
        if reflection:
            is_sufficient = reflection.get("is_sufficient", False)
            if is_sufficient:
                return "synthesize"

        # Check loop limit
        if current_loop >= max_loops:
            logger.info(f"Max exploration loops ({max_loops}) reached, synthesizing")
            return "synthesize"

        # Continue exploring if we have follow-up queries
        if reflection and reflection.get("follow_up_queries"):
            return "continue"

        return "synthesize"

    async def _analyze_target_node(self, state: ExploreState, config: RunnableConfig) -> Dict[str, Any]:
        """Analyze the exploration target and determine target type."""
        target = state.get("target", "")
        context = state.get("context", {})

        prompt = TARGET_ANALYSIS_PROMPT.format(
            target=target,
            context=json.dumps(context, indent=2) if context else "No additional context",
        )

        response = self.llm.completion(
            messages=[
                {"role": "system", "content": EXPLORE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self.exploration_temperature,
            max_tokens=self.exploration_max_tokens,
        )

        # Parse target type from response
        target_type = "general"
        try:
            # Attempt to parse JSON from response
            response_data = json.loads(response)
            target_type = response_data.get("target_type", "general")
        except (json.JSONDecodeError, TypeError):
            # Infer target type from keywords
            target_lower = target.lower()
            if any(kw in target_lower for kw in ["code", "function", "class", "module", "implement"]):
                target_type = "code"
            elif any(kw in target_lower for kw in ["pdf", "document", "word", "doc"]):
                target_type = "document"
            elif any(kw in target_lower for kw in ["csv", "excel", "data", "table"]):
                target_type = "data"
            elif any(kw in target_lower for kw in ["image", "audio", "video", "media"]):
                target_type = "media"

        return {
            "messages": [AIMessage(content=response)],
            "target_type": target_type,
            "exploration_loops": 0,
            "max_loops": self.max_loops,
            "is_sufficient": False,
        }

    async def _generate_strategy_node(self, state: ExploreState, config: RunnableConfig) -> Dict[str, Any]:
        """Generate exploration strategy based on target analysis."""
        target = state.get("target", "")
        messages = state.get("messages", [])

        # Get analysis from previous node
        analysis = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                analysis = msg.content
                break

        prompt = STRATEGY_GENERATION_PROMPT.format(
            target=target,
            analysis=analysis,
        )

        response = self.llm.completion(
            messages=[
                {"role": "system", "content": EXPLORE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self.exploration_temperature,
            max_tokens=self.exploration_max_tokens,
        )

        # Parse search strategy from response
        search_strategy = []
        try:
            # Try to extract strategy from structured response
            response_lines = response.split("\n")
            for line in response_lines:
                if "query" in line.lower() or "search" in line.lower():
                    search_strategy.append({"query": line.strip(), "priority": "medium"})
        except Exception:
            # Fallback: create basic strategy from target
            search_strategy = [{"query": target, "priority": "high"}]

        return {
            "messages": state.get("messages", []) + [AIMessage(content=response)],
            "search_strategy": search_strategy,
        }

    async def _explore_sources_node(self, state: ExploreState, config: RunnableConfig) -> Dict[str, Any]:
        """Explore sources using actual tools."""
        target = state.get("target", "")
        current_loop = state.get("exploration_loops", 0)
        reflection = state.get("reflection")

        # Get follow-up queries from reflection if available
        follow_up_queries = []
        if reflection:
            follow_up_queries = reflection.get("follow_up_queries", [])

        # Ensure tool helper is ready
        tool_helper = await self._ensure_tool_helper()

        # Get existing findings and sources
        findings = list(state.get("findings", []))
        sources = list(state.get("sources", []))
        tool_results = []

        # Determine search queries
        search_queries = follow_up_queries if follow_up_queries else [target]

        for query in search_queries[:3]:  # Limit queries per loop
            # Strategy 1: Search for relevant files
            try:
                # Use correct parameter names: pattern, directory
                search_result = await tool_helper.execute_tool(
                    "file_edit:search_in_files",
                    pattern=query,
                    directory=".",
                )
                tool_results.append(
                    {
                        "tool": "search_in_files",
                        "query": query,
                        "success": True,
                        "result": search_result[:500] if isinstance(search_result, str) else str(search_result)[:500],
                    }
                )

                # Parse search results from string (format: "file:line: content")
                if isinstance(search_result, str) and not search_result.startswith("Error"):
                    lines = search_result.strip().split("\n")
                    for line in lines[:10]:  # Limit to 10 matches
                        if ":" in line:
                            parts = line.split(":", 2)
                            if len(parts) >= 2:
                                file_name = parts[0].strip()
                                context = parts[-1].strip() if len(parts) > 2 else ""
                                finding_id = f"finding-{uuid7str()[:8]}"
                                findings.append(
                                    {
                                        "finding_id": finding_id,
                                        "title": f"Found in {file_name}",
                                        "description": context[:200],
                                        "source": file_name,
                                        "relevance": "high",
                                        "finding_type": "fact",
                                        "details": {"line": line},
                                    }
                                )
                                if file_name not in [s.get("location") for s in sources]:
                                    sources.append(
                                        {
                                            "source_id": f"source-{uuid7str()[:8]}",
                                            "type": "file",
                                            "name": file_name,
                                            "location": file_name,
                                            "summary": context[:100],
                                            "accessed_at": uuid7str(),
                                        }
                                    )
            except Exception as e:
                logger.warning(f"Search failed for query '{query}': {e}")
                tool_results.append(
                    {
                        "tool": "search_in_files",
                        "query": query,
                        "success": False,
                        "error": str(e),
                    }
                )

        # Strategy 2: List relevant files (only on first loop)
        if current_loop == 0:
            try:
                # Use correct parameter names: directory, pattern
                list_result = await tool_helper.execute_tool(
                    "file_edit:list_files",
                    directory=".",
                    pattern="*",  # List all files
                )
                tool_results.append(
                    {
                        "tool": "list_files",
                        "success": True,
                        "result": list_result[:500] if isinstance(list_result, str) else str(list_result)[:500],
                    }
                )

                # Parse list results from string
                if (
                    isinstance(list_result, str)
                    and not list_result.startswith("Error")
                    and not list_result.startswith("No files")
                ):
                    lines = list_result.strip().split("\n")
                    for line in lines[:20]:
                        file_name = line.strip()
                        if file_name:
                            # Extract just the filename if it has formatting like "[FILE] name"
                            if file_name.startswith("["):
                                file_name = file_name.split("]")[-1].strip()
                            if file_name and file_name not in [s.get("location") for s in sources]:
                                sources.append(
                                    {
                                        "source_id": f"source-{uuid7str()[:8]}",
                                        "type": "file",
                                        "name": file_name,
                                        "location": file_name,
                                        "summary": "Discovered during exploration",
                                        "accessed_at": uuid7str(),
                                    }
                                )
            except Exception as e:
                logger.warning(f"List files failed: {e}")

        # Strategy 3: Read key files found in search
        key_files = set()
        for finding in findings[-5:]:  # Last 5 findings
            if finding.get("source"):
                key_files.add(finding["source"])

        for file_path in list(key_files)[:3]:
            try:
                read_result = await tool_helper.execute_tool(
                    "file_edit:read_file",
                    file_path=file_path,
                )
                content = read_result if isinstance(read_result, str) else str(read_result)
                tool_results.append(
                    {
                        "tool": "read_file",
                        "file_path": file_path,
                        "success": True,
                        "size": len(content),
                    }
                )

                finding_id = f"finding-{uuid7str()[:8]}"
                findings.append(
                    {
                        "finding_id": finding_id,
                        "title": f"Content of {file_path}",
                        "description": content[:500],
                        "source": file_path,
                        "relevance": "medium",
                        "finding_type": "reference",
                        "details": {"full_content": content[:2000]},
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")

        return {
            "findings": findings,
            "sources": sources,
            "tool_results": tool_results,
            "exploration_loops": current_loop + 1,
        }

    async def _reflect_node(self, state: ExploreState, config: RunnableConfig) -> Dict[str, Any]:
        """Reflect on exploration progress and decide whether to continue."""
        target = state.get("target", "")
        findings = state.get("findings", [])
        sources = state.get("sources", [])
        current_loop = state.get("exploration_loops", 0)
        max_loops = state.get("max_loops", self.max_loops)

        # Format findings and sources for prompt
        findings_text = self._format_findings(findings)
        sources_text = self._format_sources(sources)

        prompt = REFLECTION_PROMPT.format(
            target=target,
            findings=findings_text,
            sources=sources_text,
            current_loop=current_loop,
            max_loops=max_loops,
        )

        response = self.llm.completion(
            messages=[
                {"role": "system", "content": EXPLORE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,  # Lower temperature for reflection
            max_tokens=1000,
        )

        # Parse reflection result
        reflection = {
            "is_sufficient": False,
            "knowledge_gaps": [],
            "follow_up_queries": [],
            "confidence": 0.5,
            "reasoning": response,
        }

        try:
            # Try to parse JSON response
            response_data = json.loads(response)
            reflection = {
                "is_sufficient": response_data.get("is_sufficient", False),
                "knowledge_gaps": response_data.get("knowledge_gaps", []),
                "follow_up_queries": response_data.get("follow_up_queries", []),
                "confidence": response_data.get("confidence", 0.5),
                "reasoning": response_data.get("reasoning", response),
            }
        except (json.JSONDecodeError, TypeError):
            # Parse from text response
            response_lower = response.lower()
            if "sufficient" in response_lower and "not" not in response_lower.split("sufficient")[0][-20:]:
                reflection["is_sufficient"] = True
            # Extract confidence from text
            if "confidence" in response_lower:
                try:
                    import re

                    match = re.search(r"confidence[:\s]+(\d+\.?\d*)", response_lower)
                    if match:
                        reflection["confidence"] = float(match.group(1))
                except Exception:
                    pass

        return {
            "reflection": reflection,
            "is_sufficient": reflection["is_sufficient"],
            "confidence_score": reflection["confidence"],
        }

    async def _synthesize_node(self, state: ExploreState, config: RunnableConfig) -> Dict[str, Any]:
        """Synthesize findings into a comprehensive summary."""
        target = state.get("target", "")
        target_type = state.get("target_type", "general")
        findings = state.get("findings", [])
        sources = state.get("sources", [])
        exploration_loops = state.get("exploration_loops", 0)
        confidence_score = state.get("confidence_score", 0.5)

        # Format findings and sources for prompt
        findings_text = self._format_findings(findings)
        sources_text = self._format_sources(sources)

        prompt = SYNTHESIS_PROMPT.format(
            target=target,
            findings=findings_text,
            sources=sources_text,
            exploration_depth=exploration_loops,
        )

        response = self.llm.completion(
            messages=[
                {"role": "system", "content": EXPLORE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self.exploration_temperature,
            max_tokens=self.exploration_max_tokens,
        )

        # Build structured ExploreResult
        structured_findings = []
        for f in findings:
            structured_findings.append(
                Finding(
                    finding_id=f.get("finding_id", f"finding-{uuid7str()[:8]}"),
                    title=f.get("title", "Unknown"),
                    description=f.get("description", ""),
                    source=f.get("source", "unknown"),
                    relevance=f.get("relevance", "medium"),
                    finding_type=f.get("finding_type", "fact"),
                    details=f.get("details", {}),
                )
            )

        structured_sources = []
        for s in sources:
            structured_sources.append(
                Source(
                    source_id=s.get("source_id", f"source-{uuid7str()[:8]}"),
                    type=s.get("type", "file"),
                    name=s.get("name", "unknown"),
                    location=s.get("location", ""),
                    summary=s.get("summary", ""),
                    accessed_at=s.get("accessed_at", ""),
                )
            )

        explore_result = ExploreResult(
            target=target,
            summary=response,
            findings=structured_findings,
            sources=structured_sources,
            confidence_score=confidence_score,
            exploration_depth=exploration_loops,
            metadata={
                "target_type": target_type,
                "max_loops": state.get("max_loops", self.max_loops),
            },
        )

        return {
            "messages": state.get("messages", []) + [AIMessage(content=response)],
            "summary": response,
            "explore_result": explore_result.model_dump(),
        }

    def _format_findings(self, findings: List[Dict[str, Any]]) -> str:
        """Format findings for prompts."""
        formatted = []
        for i, finding in enumerate(findings, 1):
            formatted.append(
                f"{i}. {finding.get('title', 'Unknown')}\n"
                f"   Description: {finding.get('description', 'No description')[:200]}\n"
                f"   Source: {finding.get('source', 'Unknown')}\n"
                f"   Relevance: {finding.get('relevance', 'medium')}\n"
                f"   Type: {finding.get('finding_type', 'fact')}"
            )
        return "\n\n".join(formatted) if formatted else "No findings yet"

    def _format_sources(self, sources: List[Dict[str, Any]]) -> str:
        """Format sources for prompts."""
        formatted = []
        seen = set()
        for source in sources:
            loc = source.get("location", "unknown")
            if loc in seen:
                continue
            seen.add(loc)
            formatted.append(
                f"- [{source.get('type', 'unknown')}] {source.get('name', 'unknown')}\n"
                f"  Location: {loc}\n"
                f"  Summary: {source.get('summary', 'No summary')[:100]}"
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
            "target_type": "general",
            "search_strategy": [],
            "findings": [],
            "sources": [],
            "tool_results": [],
            "reflection": None,
            "exploration_loops": 0,
            "max_loops": self.max_loops,
            "is_sufficient": False,
            "summary": None,
            "confidence_score": 0.0,
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
            "target_type": "general",
            "search_strategy": [],
            "findings": [],
            "sources": [],
            "tool_results": [],
            "reflection": None,
            "exploration_loops": 0,
            "max_loops": self.max_loops,
            "is_sufficient": False,
            "summary": None,
            "confidence_score": 0.0,
        }

        try:
            # Stream graph execution
            total_findings = 0
            total_sources = 0
            current_loop = 0

            async for event in self.graph.astream(initial_state):
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue

                    if node_name == "analyze_target":
                        target_type = node_output.get("target_type", "general")
                        yield ProgressEvent(
                            type=ProgressEventType.THINKING,
                            session_id=session_id,
                            summary=f"Target analysis: {target_type} type detected",
                        )

                    elif node_name == "generate_strategy":
                        yield ProgressEvent(
                            type=ProgressEventType.THINKING,
                            session_id=session_id,
                            summary="Generating exploration strategy...",
                        )

                    elif node_name == "explore_sources":
                        findings = node_output.get("findings", [])
                        sources = node_output.get("sources", [])
                        tool_results = node_output.get("tool_results", [])
                        current_loop = node_output.get("exploration_loops", 0)

                        total_findings = len(findings)
                        total_sources = len(sources)

                        # Yield step events for exploration
                        yield ProgressEvent(
                            type=ProgressEventType.STEP_START,
                            session_id=session_id,
                            step_index=current_loop - 1,
                            summary=f"Exploration loop {current_loop}/{self.max_loops}",
                        )

                        # Emit tool events based on actual tool execution
                        for tool_result in tool_results:
                            tool_name = tool_result.get("tool", "unknown")
                            success = tool_result.get("success", False)

                            yield ProgressEvent(
                                type=ProgressEventType.TOOL_START,
                                session_id=session_id,
                                tool_name=tool_name,
                                summary=f"Executing {tool_name}...",
                            )

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
                        yield ProgressEvent(
                            type=ProgressEventType.PARTIAL_RESULT,
                            session_id=session_id,
                            text=f"Loop {current_loop}: {total_findings} findings, {total_sources} sources",
                            summary=f"Found {total_findings} findings",
                        )

                    elif node_name == "reflect":
                        reflection = node_output.get("reflection", {})
                        is_sufficient = reflection.get("is_sufficient", False)
                        confidence = reflection.get("confidence", 0.5)
                        gaps = reflection.get("knowledge_gaps", [])

                        yield ProgressEvent(
                            type=ProgressEventType.THINKING,
                            session_id=session_id,
                            summary=f"Reflection: {'sufficient' if is_sufficient else 'need more'} (confidence: {confidence:.1%})",
                        )

                        if gaps:
                            yield ProgressEvent(
                                type=ProgressEventType.PARTIAL_RESULT,
                                session_id=session_id,
                                text=f"Knowledge gaps: {', '.join(gaps[:3])}",
                                summary="Identified gaps",
                            )

                    elif node_name == "synthesize":
                        yield ProgressEvent(
                            type=ProgressEventType.THINKING,
                            session_id=session_id,
                            summary="Synthesizing findings...",
                        )

                        summary = node_output.get("summary", "")

                        # Yield final answer
                        yield ProgressEvent(
                            type=ProgressEventType.FINAL_ANSWER,
                            session_id=session_id,
                            text=summary,
                            summary=f"Complete: {total_findings} findings, {total_sources} sources, {current_loop} loops",
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

    async def explore(
        self,
        target: str,
        context: Dict[str, Any] = None,
    ) -> ExploreResult:
        """Run exploration and return structured result.

        Args:
            target: What to explore
            context: Additional context

        Returns:
            ExploreResult with structured findings
        """
        initial_state: ExploreState = {
            "messages": [HumanMessage(content=target)],
            "context": context or {},
            "target": target,
            "target_type": "general",
            "search_strategy": [],
            "findings": [],
            "sources": [],
            "tool_results": [],
            "reflection": None,
            "exploration_loops": 0,
            "max_loops": self.max_loops,
            "is_sufficient": False,
            "summary": None,
            "confidence_score": 0.0,
        }

        result = await self.graph.ainvoke(initial_state)

        # Return structured result
        explore_result_data = result.get("explore_result", {})
        if explore_result_data:
            return ExploreResult(**explore_result_data)

        # Fallback: construct from state
        return ExploreResult(
            target=target,
            summary=result.get("summary", "Exploration failed"),
            findings=[],
            sources=[],
            confidence_score=result.get("confidence_score", 0.0),
            exploration_depth=result.get("exploration_loops", 0),
            metadata={},
        )
