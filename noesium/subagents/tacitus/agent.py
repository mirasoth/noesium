"""
TacitusAgent implementation using LangGraph and LLM integration.
Enhanced base class designed for extensibility.
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Type

try:
    from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
    from langchain_core.runnables import RunnableConfig
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Send

    LANGCHAIN_AVAILABLE = True
except ImportError:
    AIMessage = None
    AnyMessage = None
    HumanMessage = None
    RunnableConfig = None
    StateGraph = None
    END = None
    START = None
    Send = None
    LANGCHAIN_AVAILABLE = False

from noesium.core.agent import BaseResearcher, ResearchOutput
from noesium.core.llm import BaseLLMClient
from noesium.core.utils.logging import get_logger
from noesium.core.utils.typing import override

from .prompts import answer_instructions, query_writer_instructions, reflection_instructions
from .schemas import Reflection, SearchQueryList
from .state import QueryState, ReflectionState, ResearchState, WebSearchState

# Configure logging
logger = get_logger(__name__)


def get_current_date() -> str:
    """Get current date in a readable format."""
    return datetime.now().strftime("%B %d, %Y")


class TacitusAgent(BaseResearcher):
    """
    Advanced research agent using LangGraph and LLM integration.
    """

    def __init__(
        self,
        llm_provider: str = "openai",
        query_generation_llm: BaseLLMClient | None = None,
        reflection_llm: BaseLLMClient | None = None,
        number_of_initial_queries: int = 2,
        max_research_loops: int = 2,
        query_generation_temperature: float = 0.7,
        query_generation_max_tokens: int = 1000,
        web_search_temperature: float = 0.2,
        web_search_max_tokens: int = 3000,
        web_search_citation_enabled: bool = True,
        reflection_temperature: float = 0.5,
        reflection_max_tokens: int = 1000,
        answer_temperature: float = 0.3,
        answer_max_tokens: int = 10000,
        search_engines: List[str] = ["tavily"],
        max_results_per_engine: int = 5,
        search_timeout: int = 20,
    ):
        """
        Initialize the TacitusAgent.
        """
        # Initialize base class
        super().__init__(llm_provider=llm_provider)

        # Override the LLM client with instructor support if needed
        # Base class already initializes self.llm, so we can reuse it
        self.llm_client = self.llm
        self.query_generation_llm = query_generation_llm if query_generation_llm else self.llm
        self.reflection_llm = reflection_llm if reflection_llm else self.llm
        self.number_of_initial_queries = number_of_initial_queries
        self.max_research_loops = max_research_loops
        self.query_generation_temperature = query_generation_temperature
        self.query_generation_max_tokens = query_generation_max_tokens
        self.web_search_temperature = web_search_temperature
        self.web_search_max_tokens = web_search_max_tokens
        self.web_search_citation_enabled = web_search_citation_enabled
        self.reflection_temperature = reflection_temperature
        self.reflection_max_tokens = reflection_max_tokens
        self.answer_temperature = answer_temperature
        self.answer_max_tokens = answer_max_tokens
        self.search_engines = search_engines
        self.max_results_per_engine = max_results_per_engine
        self.search_timeout = search_timeout

        # Load prompts (can be overridden by subclasses)
        self.prompts = self.get_prompts()

        # Create the research graph
        self.graph = self._build_graph()

    @override
    def get_state_class(self) -> Type:
        """
        Get the state class for this researcher.
        Override this method in subclasses for specialized state.

        Returns:
            The state class to use for the research workflow
        """
        return ResearchState

    @override
    def _build_graph(self) -> StateGraph:
        """Create the LangGraph research workflow."""
        state_class = self.get_state_class()
        workflow = StateGraph(state_class)

        # Add nodes
        workflow.add_node("generate_query", self._generate_query_node)
        workflow.add_node("web_research", self._research_node)
        workflow.add_node("reflection", self._reflection_node)
        workflow.add_node("finalize_answer", self._finalize_answer_node)

        # Set entry point
        workflow.add_edge(START, "generate_query")

        # Add conditional edges
        workflow.add_conditional_edges("generate_query", self._continue_to_web_research, ["web_research"])
        workflow.add_edge("web_research", "reflection")
        workflow.add_conditional_edges("reflection", self._evaluate_research, ["web_research", "finalize_answer"])
        workflow.add_edge("finalize_answer", END)

        return workflow.compile()

    @override
    async def research(
        self,
        user_message: str,
        context: Dict[str, Any] = None,
        config: Optional[RunnableConfig] = None,
    ) -> ResearchOutput:
        """
        Research a topic and return structured results.

        Args:
            user_message: User's research request
            context: Additional context for research
            config: Optional RunnableConfig for runtime configuration

        Returns:
            ResearchOutput with content and sources
        """
        try:
            # Initialize state (can be customized by subclasses)
            initial_state = {
                "messages": [HumanMessage(content=user_message)],
                "context": context,
                "search_query": [],
                "web_research_result": [],
                "sources_gathered": [],
                "initial_search_query_count": self.number_of_initial_queries,
                "max_research_loops": self.max_research_loops,
                "research_loop_count": 0,
            }
            # Run the research graph with optional runtime configuration
            if config:
                result = await self.graph.ainvoke(initial_state, config=config)
            else:
                result = await self.graph.ainvoke(initial_state)

            # Extract the final AI message
            final_message = None
            for message in reversed(result["messages"]):
                if isinstance(message, AIMessage):
                    final_message = message.content
                    break

            return ResearchOutput(
                content=final_message or "Research completed",
                sources=result.get("sources_gathered", []),
                summary=f"Research completed for topic",
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error in research: {e}")
            raise RuntimeError(f"Research failed: {str(e)}")

    def get_prompts(self) -> Dict[str, str]:
        """
        Get prompts for the researcher.
        Override this method in subclasses for specialized prompts.

        Returns:
            Dictionary containing all prompts for the research workflow
        """
        return {
            "query_writer": query_writer_instructions,
            "reflection": reflection_instructions,
            "answer": answer_instructions,
        }

    def _preprocess_research_topic(self, messages: List[AnyMessage]) -> str:
        """
        Get the research topic from the messages.

        Args:
            messages: List of messages from the conversation

        Returns:
            Formatted research topic string
        """
        # Check if request has a history and combine the messages into a single string
        if len(messages) == 1:
            research_topic = messages[-1].content
        else:
            research_topic = ""
            for message in messages:
                if isinstance(message, HumanMessage):
                    research_topic += f"User: {message.content}\n"
                elif isinstance(message, AIMessage):
                    research_topic += f"Assistant: {message.content}\n"
        return research_topic

    def _generate_query_node(self, state: ResearchState, config: RunnableConfig) -> QueryState:
        """Generate search queries based on user request using instructor structured output."""
        # Get research topic from messages (can be customized by subclasses)
        research_topic = self._preprocess_research_topic(state["messages"])

        # Format the prompt
        current_date = get_current_date()
        formatted_prompt = self.prompts["query_writer"].format(
            current_date=current_date,
            research_topic=research_topic,
            number_queries=state.get("initial_search_query_count", self.number_of_initial_queries),
        )

        try:
            # Generate queries using instructor with structured output
            result: SearchQueryList = self.llm_client.structured_completion(
                messages=[{"role": "user", "content": formatted_prompt}],
                response_model=SearchQueryList,
                temperature=self.query_generation_temperature,
                max_tokens=self.query_generation_max_tokens,
            )

            logger.info(f"Generated {len(result.query)} queries: {result.query}, rationale: {result.rationale}")

            # Create query list with rationale
            query_list = [{"query": q, "rationale": result.rationale} for q in result.query]
            return {"query_list": query_list}

        except Exception as e:
            raise RuntimeError(f"Error in structured query generation: {e}")

    def _continue_to_web_research(self, state: QueryState) -> List[Send]:
        """Send queries to web research nodes."""
        return [
            Send(
                "web_research",
                WebSearchState(search_query=item["query"], id=str(idx)),
            )
            for idx, item in enumerate(state["query_list"])
        ]

    async def _research_node(self, state: WebSearchState, config: RunnableConfig) -> ResearchState:
        """Perform web research using Tavily Search API."""
        search_query = state["search_query"]

        try:
            from wizsearch import WizSearch, WizSearchConfig

            omnisearch = WizSearch(
                config=WizSearchConfig(
                    enabled_engines=self.search_engines,
                    max_results_per_engine=self.max_results_per_engine,
                    timeout=self.search_timeout,
                )
            )

            result = await omnisearch.search(query=search_query)

            # Convert SearchResult objects to dictionaries for compatibility
            sources_gathered = []
            for source in result.sources:
                sources_gathered.append(source.model_dump())

            # Generate research summary based on actual search results
            if sources_gathered:
                # Create a summary from the actual content found
                content_summary = "\n\n".join(
                    [f"Source: {s['title']}\n{s['content']}" for s in sources_gathered[:5]]  # Use top 5 results
                )

                summary_prompt = f"""
                Based on the following search results for "{search_query}", provide a concise and accurate research summary:

                {content_summary}

                Please provide a well-structured summary that:
                1. Addresses the search query directly
                2. Synthesizes information from multiple sources
                3. Highlights key findings and insights
                4. Maintains factual accuracy based on the provided content
                """

                search_summary = self.llm_client.completion(
                    messages=[{"role": "user", "content": summary_prompt}],
                    temperature=self.web_search_temperature,
                    max_tokens=self.web_search_max_tokens,
                )
            else:
                search_summary = f"No relevant sources found for: {search_query}"

            return ResearchState(
                sources_gathered=sources_gathered,
                search_query=[search_query],
                search_summaries=[search_summary],
            )

        except Exception as e:
            logger.error(f"Error in Tavily web search: {e}")
            raise RuntimeError(f"Tavily web search failed: {str(e)}")

    def _reflection_node(self, state: ResearchState, config: RunnableConfig) -> ReflectionState:
        """Reflect on research results and identify gaps using instructor structured output."""
        # Increment research loop count
        research_loop_count = state.get("research_loop_count", 0) + 1

        # Format the prompt
        current_date = get_current_date()
        research_topic = self._preprocess_research_topic(state["messages"])
        summaries = "\n\n---\n\n".join(state.get("search_summaries", []))

        formatted_prompt = self.prompts["reflection"].format(
            current_date=current_date,
            research_topic=research_topic,
            summaries=summaries,
        )

        try:
            # Use instructor for reflection and evaluation with structured output
            result: Reflection = self.llm_client.structured_completion(
                messages=[{"role": "user", "content": formatted_prompt}],
                response_model=Reflection,
                temperature=self.reflection_temperature,
                max_tokens=self.reflection_max_tokens,
            )

            return ReflectionState(
                is_sufficient=result.is_sufficient,
                knowledge_gap=result.knowledge_gap,
                follow_up_queries=result.follow_up_queries,
                research_loop_count=research_loop_count,
                number_of_ran_queries=len(state.get("search_query", [])),
            )

        except Exception as e:
            raise RuntimeError(f"Error in structured reflection: {e}")

    def _evaluate_research(self, state: ReflectionState, config: RunnableConfig):
        """Evaluate research and decide next step."""

        if state["is_sufficient"] or state["research_loop_count"] >= self.max_research_loops:
            return "finalize_answer"
        else:
            return [
                Send(
                    "web_research",
                    WebSearchState(search_query=follow_up_query, id=str(state["number_of_ran_queries"] + int(idx))),
                )
                for idx, follow_up_query in enumerate(state["follow_up_queries"])
            ]

    def _finalize_answer_node(self, state: ResearchState, config: RunnableConfig):
        """Finalize the research answer with advanced formatting and citations."""
        current_date = get_current_date()
        research_topic = self._preprocess_research_topic(state["messages"])
        summaries = "\n---\n\n".join(state.get("search_summaries", []))

        formatted_prompt = self.prompts["answer"].format(
            current_date=current_date,
            research_topic=research_topic,
            summaries=summaries,
        )

        # Generate final answer using LLM
        final_answer = self.llm_client.completion(
            messages=[{"role": "user", "content": formatted_prompt}],
            temperature=self.answer_temperature,
            max_tokens=self.answer_max_tokens,
        )

        return {
            "messages": [AIMessage(content=final_answer)],
            "sources_gathered": state.get("sources_gathered", []),
        }

    async def astream_progress(
        self,
        user_message: str,
        context: Dict[str, Any] = None,
        config: Optional[RunnableConfig] = None,
    ) -> AsyncGenerator[Any, None]:
        """Stream progress events during research.

        This method yields ProgressEvent objects compatible with NoeAgent's
        progress system, allowing real-time visibility into research phases.

        Args:
            user_message: User's research request
            context: Additional context for research
            config: Optional RunnableConfig for runtime configuration

        Yields:
            ProgressEvent: Events describing research progress.

        Event Sequence:
            1. SESSION_START - Research initiated
            2. PLAN_CREATED - Research plan (queries to generate)
            3. STEP_START - For each query generation
            4. TOOL_START/TOOL_END - For web searches
            5. THINKING - During reflection
            6. FINAL_ANSWER - Research summary
            7. SESSION_END - Complete
        """
        # Lazy import to avoid circular dependencies
        from uuid_extensions import uuid7str

        from noesium.noeagent.progress import ProgressEvent, ProgressEventType

        session_id = uuid7str()

        # Yield SESSION_START
        yield ProgressEvent(
            type=ProgressEventType.SESSION_START,
            session_id=session_id,
            summary=f"Research: {user_message[:60]}",
        )

        # Initialize state
        initial_state = {
            "messages": [HumanMessage(content=user_message)],
            "context": context,
            "search_query": [],
            "web_research_result": [],
            "sources_gathered": [],
            "initial_search_query_count": self.number_of_initial_queries,
            "max_research_loops": self.max_research_loops,
            "research_loop_count": 0,
        }

        try:
            # Stream graph execution
            current_loop = 0
            total_sources = 0
            final_content = None

            # Yield thinking event before starting
            yield ProgressEvent(
                type=ProgressEventType.THINKING,
                session_id=session_id,
                summary="Analyzing research topic...",
            )

            async for event in self.graph.astream(initial_state):
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue

                    # Generate query node
                    if node_name == "generate_query":
                        query_list = node_output.get("query_list", [])
                        queries_generated = len(query_list)

                        # Yield PLAN_CREATED with query steps
                        yield ProgressEvent(
                            type=ProgressEventType.PLAN_CREATED,
                            session_id=session_id,
                            summary=f"Generated {queries_generated} search queries",
                            plan_snapshot={
                                "steps": [
                                    {"description": f"Search: {q['query'][:50]}", "status": "pending"}
                                    for q in query_list
                                ],
                                "goal": user_message,
                            },
                        )

                        # Yield step events for each query
                        for i, q in enumerate(query_list):
                            yield ProgressEvent(
                                type=ProgressEventType.STEP_START,
                                session_id=session_id,
                                step_index=i,
                                summary=f"🔍 Query {i+1}/{queries_generated}: {q['query'][:40]}",
                            )

                    # Web research node
                    elif node_name == "web_research":
                        search_query = node_output.get("search_query", [])
                        sources = node_output.get("sources_gathered", [])

                        for query in search_query:
                            yield ProgressEvent(
                                type=ProgressEventType.TOOL_START,
                                session_id=session_id,
                                tool_name="web_search",
                                summary=f"🔎 Searching: {query[:50]}",
                            )

                        if sources:
                            total_sources += len(sources)
                            yield ProgressEvent(
                                type=ProgressEventType.TOOL_END,
                                session_id=session_id,
                                tool_name="web_search",
                                tool_result=f"Found {len(sources)} sources",
                                summary=f"✓ Found {len(sources)} sources (total: {total_sources})",
                            )

                    # Reflection node
                    elif node_name == "reflection":
                        is_sufficient = node_output.get("is_sufficient", False)
                        current_loop = node_output.get("research_loop_count", 0)
                        knowledge_gap = node_output.get("knowledge_gap", "")

                        # Yield thinking event for reflection
                        yield ProgressEvent(
                            type=ProgressEventType.THINKING,
                            session_id=session_id,
                            summary=f"Reflecting on research (loop {current_loop}/{self.max_research_loops})...",
                        )

                        # Yield reflection result
                        if is_sufficient:
                            yield ProgressEvent(
                                type=ProgressEventType.REFLECTION,
                                session_id=session_id,
                                text="Research is sufficient, proceeding to finalize.",
                                summary="✓ Research sufficient",
                            )
                        else:
                            gap_text = knowledge_gap[:50] if knowledge_gap else "more research needed"
                            follow_up_queries = node_output.get("follow_up_queries", [])
                            if follow_up_queries:
                                # Emit plan snapshot so TUI can show second-round (follow-up) steps
                                yield ProgressEvent(
                                    type=ProgressEventType.PLAN_REVISED,
                                    session_id=session_id,
                                    summary=f"Need more research: {gap_text}",
                                    detail=knowledge_gap,
                                    plan_snapshot={
                                        "steps": [
                                            {"description": f"Search: {q[:50]}", "status": "pending"}
                                            for q in follow_up_queries
                                        ],
                                        "goal": user_message,
                                    },
                                )
                            else:
                                yield ProgressEvent(
                                    type=ProgressEventType.PLAN_REVISED,
                                    session_id=session_id,
                                    summary=f"Need more research: {gap_text}",
                                    detail=knowledge_gap,
                                )

                    # Finalize answer node
                    elif node_name == "finalize_answer":
                        messages = node_output.get("messages", [])
                        sources = node_output.get("sources_gathered", [])

                        # Extract final content
                        for msg in reversed(messages):
                            if hasattr(msg, "content"):
                                final_content = msg.content
                                break

                        # Yield thinking before finalizing
                        yield ProgressEvent(
                            type=ProgressEventType.THINKING,
                            session_id=session_id,
                            summary="Synthesizing final answer...",
                        )

                        # Yield final answer
                        yield ProgressEvent(
                            type=ProgressEventType.FINAL_ANSWER,
                            session_id=session_id,
                            text=final_content or "Research completed",
                            summary=f"Research complete ({total_sources} sources)",
                            detail=f"Sources: {[s.get('url', s.get('title', 'unknown')) for s in sources[:5]]}",
                        )

        except Exception as e:
            logger.error(f"Research failed: {e}")
            yield ProgressEvent(
                type=ProgressEventType.ERROR,
                session_id=session_id,
                error=str(e),
                summary=f"Research failed: {str(e)[:60]}",
            )
            raise

        finally:
            # Yield SESSION_END
            yield ProgressEvent(
                type=ProgressEventType.SESSION_END,
                session_id=session_id,
            )
