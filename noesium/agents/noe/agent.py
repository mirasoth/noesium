"""Noet -- autonomous research assistant (impl guide §5.1)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, Optional, Type

try:
    from langchain_core.messages import HumanMessage
    from langchain_core.runnables import RunnableConfig
    from langgraph.graph import END, START, StateGraph
except ImportError:
    raise ImportError(
        "Noet requires langchain-core and langgraph. "
        "Install them with: uv run pip install langchain-core langgraph"
    )

from noesium.core.agent.base import BaseGraphicAgent
from noesium.core.event.envelope import AgentRef
from noesium.core.event.store import InMemoryEventStore
from noesium.core.memory.provider import MemoryTier
from noesium.core.memory.provider_manager import ProviderMemoryManager
from noesium.core.memory.providers.event_sourced import EventSourcedProvider
from noesium.core.memory.providers.working import WorkingMemoryProvider
from noesium.core.toolify.adapters.builtin_adapter import BuiltinAdapter
from noesium.core.toolify.adapters.function_adapter import FunctionAdapter
from noesium.core.toolify.atomic import ToolContext, ToolPermission
from noesium.core.toolify.executor import ToolExecutor
from noesium.core.toolify.tool_registry import ToolRegistry

from . import nodes
from .config import NoeConfig, NoeMode
from .planner import TaskPlanner
from .state import AgentState, AskState

logger = logging.getLogger(__name__)


class NoeAgent(BaseGraphicAgent):
    """Long-running autonomous research assistant.

    Operates in two modes:
      * **Ask**: Single-turn, read-only Q&A (no tools, no side effects).
      * **Agent**: Full autonomous loop with planning, tool execution,
        reflection, and memory persistence.
    """

    def __init__(self, config: NoeConfig | None = None) -> None:
        self.config = (config or NoeConfig()).effective()
        super().__init__(
            llm_provider=self.config.llm_provider,
            model_name=self.config.model_name,
        )
        self._agent_id = f"noe-{id(self)}"
        self._memory_manager: ProviderMemoryManager | None = None
        self._tool_executor: ToolExecutor | None = None
        self._tool_registry: ToolRegistry | None = None
        self._planner: TaskPlanner | None = None
        self._event_store = InMemoryEventStore()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Set up memory, tools, and event infrastructure."""
        await self._setup_memory()
        if self.config.mode == NoeMode.AGENT:
            await self._setup_tools()
            self._planner = TaskPlanner(self.llm)

    async def _setup_memory(self) -> None:
        providers = []
        if "working" in self.config.memory_providers:
            providers.append(WorkingMemoryProvider())
        if "event_sourced" in self.config.memory_providers:
            producer = AgentRef(agent_id=self._agent_id, agent_type="noe")
            providers.append(EventSourcedProvider(self._event_store, producer))
        self._memory_manager = ProviderMemoryManager(providers)

    async def _setup_tools(self) -> None:
        self._tool_registry = ToolRegistry()

        from noesium.core.toolify.registry import ToolkitRegistry

        for toolkit_name in self.config.enabled_toolkits:
            try:
                toolkit = ToolkitRegistry.create_toolkit(toolkit_name)
                tools = BuiltinAdapter.from_toolkit(toolkit, toolkit_name)
                self._tool_registry.register_many(tools)
            except Exception as exc:
                logger.warning("Failed to load toolkit %s: %s", toolkit_name, exc)

        for func in self.config.custom_tools:
            tool = FunctionAdapter.from_function(func)
            self._tool_registry.register(tool)

        self._tool_executor = ToolExecutor(
            event_store=self._event_store,
            producer=AgentRef(agent_id=self._agent_id, agent_type="noe"),
        )

    # ------------------------------------------------------------------
    # BaseGraphicAgent interface
    # ------------------------------------------------------------------

    def get_state_class(self) -> Type:
        if self.config.mode == NoeMode.ASK:
            return AskState
        return AgentState

    def _build_graph(self) -> StateGraph:
        if self.config.mode == NoeMode.ASK:
            return self._build_ask_graph()
        return self._build_agent_graph()

    # ------------------------------------------------------------------
    # Ask-mode graph
    # ------------------------------------------------------------------

    def _build_ask_graph(self) -> StateGraph:
        workflow = StateGraph(AskState)

        async def _recall(state: AskState) -> dict:
            return await nodes.recall_memory_node(state, memory_manager=self._memory_manager)

        async def _answer(state: AskState) -> dict:
            return await nodes.generate_answer_node(state, llm=self.llm)

        workflow.add_node("recall_memory", _recall)
        workflow.add_node("generate_answer", _answer)
        workflow.add_edge(START, "recall_memory")
        workflow.add_edge("recall_memory", "generate_answer")
        workflow.add_edge("generate_answer", END)

        return workflow

    # ------------------------------------------------------------------
    # Agent-mode graph
    # ------------------------------------------------------------------

    def _build_agent_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        tool_names = [t.name for t in (self._tool_registry.list_tools() if self._tool_registry else [])]

        async def _plan(state: AgentState) -> dict:
            return await nodes.plan_node(state, planner=self._planner)

        async def _execute(state: AgentState) -> dict:
            return await nodes.execute_step_node(state, llm=self.llm, tool_names=tool_names)

        async def _tools(state: AgentState) -> dict:
            ctx = ToolContext(
                agent_id=self._agent_id,
                granted_permissions=[ToolPermission(p) for p in self.config.permissions],
                working_directory=self.config.working_directory,
            )
            return await nodes.tool_node(
                state,
                tool_registry=self._tool_registry,
                tool_executor=self._tool_executor,
                context=ctx,
            )

        async def _reflect(state: AgentState) -> dict:
            return await nodes.reflect_node(state, llm=self.llm)

        async def _revise(state: AgentState) -> dict:
            return await nodes.revise_plan_node(state, planner=self._planner)

        async def _finalize(state: AgentState) -> dict:
            return await nodes.finalize_node(state, llm=self.llm)

        workflow.add_node("plan", _plan)
        workflow.add_node("execute_step", _execute)
        workflow.add_node("tool_node", _tools)
        workflow.add_node("reflect", _reflect)
        workflow.add_node("revise_plan", _revise)
        workflow.add_node("finalize", _finalize)

        workflow.add_edge(START, "plan")
        workflow.add_edge("plan", "execute_step")
        workflow.add_conditional_edges(
            "execute_step",
            self._route_after_execute,
            {"tool_node": "tool_node", "reflect": "reflect", "finalize": "finalize", "execute_step": "execute_step"},
        )
        workflow.add_edge("tool_node", "execute_step")
        workflow.add_conditional_edges(
            "reflect",
            self._route_after_reflect,
            {"revise_plan": "revise_plan", "finalize": "finalize", "execute_step": "execute_step"},
        )
        workflow.add_edge("revise_plan", "execute_step")
        workflow.add_edge("finalize", END)

        return workflow

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _route_after_execute(self, state: AgentState) -> str:
        plan = state.get("plan")
        if plan and plan.is_complete:
            return "finalize"
        last_msg = state["messages"][-1] if state.get("messages") else None
        if last_msg and getattr(last_msg, "tool_calls", None):
            return "tool_node"
        iteration = state.get("iteration", 0)
        if iteration >= self.config.max_iterations:
            return "finalize"
        if iteration > 0 and iteration % self.config.reflection_interval == 0:
            return "reflect"
        return "execute_step"

    def _route_after_reflect(self, state: AgentState) -> str:
        reflection = state.get("reflection", "")
        if "REVISE" in reflection.upper():
            return "revise_plan"
        plan = state.get("plan")
        if plan and plan.is_complete:
            return "finalize"
        return "execute_step"

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    def run(
        self,
        user_message: str,
        context: Dict[str, Any] | None = None,
        config: Optional[RunnableConfig] = None,
    ) -> str:
        return asyncio.get_event_loop().run_until_complete(self.arun(user_message, context))

    async def arun(self, user_message: str, context: Dict[str, Any] | None = None) -> str:
        await self.initialize()
        graph = self._build_graph()
        compiled = graph.compile()
        self.graph = compiled

        initial: dict[str, Any]
        if self.config.mode == NoeMode.ASK:
            initial = {
                "messages": [HumanMessage(content=user_message)],
                "memory_context": [],
                "final_answer": "",
            }
        else:
            initial = {
                "messages": [HumanMessage(content=user_message)],
                "plan": None,
                "iteration": 0,
                "tool_results": [],
                "reflection": "",
                "final_answer": "",
            }

        result = await compiled.ainvoke(initial)

        if self.config.persist_memory and self._memory_manager:
            answer = result.get("final_answer", "")
            if answer:
                await self._memory_manager.store(
                    key=f"research:{user_message[:60]}",
                    value=answer[:1000],
                    content_type="research",
                    tier=MemoryTier.PERSISTENT,
                )

        return result.get("final_answer", "")

    async def stream(
        self,
        user_message: str,
        context: Dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        await self.initialize()
        graph = self._build_graph()
        compiled = graph.compile()
        self.graph = compiled

        initial: dict[str, Any]
        if self.config.mode == NoeMode.ASK:
            initial = {
                "messages": [HumanMessage(content=user_message)],
                "memory_context": [],
                "final_answer": "",
            }
        else:
            initial = {
                "messages": [HumanMessage(content=user_message)],
                "plan": None,
                "iteration": 0,
                "tool_results": [],
                "reflection": "",
                "final_answer": "",
            }

        async for event in compiled.astream(initial):
            for node_name, node_output in event.items():
                if "final_answer" in node_output and node_output["final_answer"]:
                    yield node_output["final_answer"]
