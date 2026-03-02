"""Noe -- autonomous research assistant (impl guide §5)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional, Type

try:
    from langchain_core.messages import HumanMessage
    from langchain_core.runnables import RunnableConfig
    from langgraph.graph import END, START, StateGraph
except ImportError:
    raise ImportError(
        "Noe requires langchain-core and langgraph. " "Install them with: uv run pip install langchain-core langgraph"
    )

from noesium.core.agent.base import BaseGraphicAgent
from noesium.core.event.envelope import AgentRef
from noesium.core.event.store import InMemoryEventStore
from noesium.core.memory.provider import MemoryTier
from noesium.core.memory.provider_manager import ProviderMemoryManager
from noesium.core.memory.providers.event_sourced import EventSourcedProvider
from noesium.core.memory.providers.memu import MemuProvider
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
    """Long-running autonomous research assistant with structured tool calling."""

    def __init__(self, config: NoeConfig | None = None) -> None:
        self.config = (config or NoeConfig()).effective()
        super().__init__(
            llm_provider=self.config.llm_provider,
        )
        self._agent_id = f"noe-{id(self)}"
        self._memory_manager: ProviderMemoryManager | None = None
        self._tool_executor: ToolExecutor | None = None
        self._tool_registry: ToolRegistry | None = None
        self._planner: TaskPlanner | None = None
        self._event_store = InMemoryEventStore()
        self._subagents: dict[str, "NoeAgent"] = {}
        self._depth: int = 0

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
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
        if "memu" in self.config.memory_providers:
            try:
                from noesium.core.memory.memu.memory_store import MemuMemoryStore

                memory_store = MemuMemoryStore(
                    memory_dir=str(Path(self.config.memu_memory_dir).resolve()),
                    agent_id=self._agent_id,
                    user_id=self.config.memu_user_id,
                )
                providers.append(
                    MemuProvider(
                        memory_store,
                        self._event_store,
                        AgentRef(agent_id=self._agent_id, agent_type="noe"),
                    )
                )
            except Exception as exc:
                logger.warning("Failed to initialize memu provider: %s", exc)
        self._memory_manager = ProviderMemoryManager(providers)

    async def _setup_tools(self) -> None:
        self._tool_registry = ToolRegistry()
        from noesium.core.toolify.base import AsyncBaseToolkit
        from noesium.core.toolify.registry import ToolkitRegistry

        for toolkit_name in self.config.enabled_toolkits:
            try:
                toolkit = ToolkitRegistry.create_toolkit(toolkit_name)
                # Initialize async toolkits
                if isinstance(toolkit, AsyncBaseToolkit):
                    await toolkit.build()
                tools = await BuiltinAdapter.from_toolkit(toolkit, toolkit_name)
                self._tool_registry.register_many(tools)
            except Exception as exc:
                logger.warning("Failed to load toolkit %s: %s", toolkit_name, exc)

        for mcp_config in self.config.mcp_servers:
            try:
                await self._tool_registry.load_mcp_server(await self._connect_mcp(mcp_config))
            except Exception as exc:
                logger.warning("Failed to load MCP server: %s", exc)

        for func in self.config.custom_tools:
            self._tool_registry.register(FunctionAdapter.from_function(func))

        self._tool_executor = ToolExecutor(
            event_store=self._event_store,
            producer=AgentRef(agent_id=self._agent_id, agent_type="noe"),
        )

    @staticmethod
    async def _connect_mcp(mcp_config: dict) -> Any:
        """Attempt to connect to an MCP server. Returns session or raises."""
        try:
            from noesium.core.toolify.mcp_session import MCPSession

            return await MCPSession.connect(**mcp_config)
        except ImportError:
            raise ImportError("MCP support requires mcp package")

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def get_state_class(self) -> Type:
        return AskState if self.config.mode == NoeMode.ASK else AgentState

    def _build_graph(self) -> StateGraph:
        if self.config.mode == NoeMode.ASK:
            return self._build_ask_graph()
        return self._build_agent_graph()

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

    def _build_agent_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        # -- node closures --------------------------------------------------

        async def _plan(state: AgentState) -> dict:
            return await nodes.plan_node(
                state,
                planner=self._planner,
                memory_manager=self._memory_manager,
            )

        async def _execute(state: AgentState) -> dict:
            return await nodes.execute_step_node(
                state,
                llm=self.llm,
                tool_registry=self._tool_registry,
                memory_manager=self._memory_manager,
            )

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

        async def _subagent(state: AgentState) -> dict:
            return await nodes.subagent_node(state, agent=self)

        async def _reflect(state: AgentState) -> dict:
            return await nodes.reflect_node(state, llm=self.llm)

        async def _revise(state: AgentState) -> dict:
            return await nodes.revise_plan_node(
                state,
                planner=self._planner,
                memory_manager=self._memory_manager,
            )

        async def _finalize(state: AgentState) -> dict:
            return await nodes.finalize_node(state, llm=self.llm)

        # -- wire graph ------------------------------------------------------

        workflow.add_node("plan", _plan)
        workflow.add_node("execute_step", _execute)
        workflow.add_node("tool_node", _tools)
        workflow.add_node("subagent_node", _subagent)
        workflow.add_node("reflect", _reflect)
        workflow.add_node("revise_plan", _revise)
        workflow.add_node("finalize", _finalize)

        workflow.add_edge(START, "plan")
        workflow.add_edge("plan", "execute_step")
        workflow.add_conditional_edges(
            "execute_step",
            self._route_after_execute,
            {
                "tool_node": "tool_node",
                "subagent_node": "subagent_node",
                "reflect": "reflect",
                "finalize": "finalize",
                "execute_step": "execute_step",
            },
        )
        workflow.add_edge("tool_node", "execute_step")
        workflow.add_edge("subagent_node", "execute_step")
        workflow.add_conditional_edges(
            "reflect",
            self._route_after_reflect,
            {
                "revise_plan": "revise_plan",
                "finalize": "finalize",
                "execute_step": "execute_step",
            },
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
        if last_msg and last_msg.additional_kwargs.get("subagent_action"):
            return "subagent_node"

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
        return "finalize" if plan and plan.is_complete else "execute_step"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        user_message: str,
        context: Dict[str, Any] | None = None,
        config: Optional[RunnableConfig] = None,
    ) -> str:
        """Synchronous entry point."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.arun(user_message, context))
        finally:
            loop.close()

    async def arun(
        self,
        user_message: str,
        context: Dict[str, Any] | None = None,
    ) -> str:
        """Async entry point."""
        await self.initialize()
        compiled = self._build_graph().compile()
        self.graph = compiled

        initial: dict[str, Any] = {
            "messages": [HumanMessage(content=user_message)],
            "final_answer": "",
        }
        if self.config.mode == NoeMode.ASK:
            initial["memory_context"] = []
        else:
            initial.update({"plan": None, "iteration": 0, "tool_results": [], "reflection": ""})

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
        """Streaming entry point for incremental output."""
        await self.initialize()
        compiled = self._build_graph().compile()
        self.graph = compiled

        initial: dict[str, Any] = {
            "messages": [HumanMessage(content=user_message)],
            "final_answer": "",
        }
        if self.config.mode == NoeMode.ASK:
            initial["memory_context"] = []
        else:
            initial.update({"plan": None, "iteration": 0, "tool_results": [], "reflection": ""})

        async for event in compiled.astream(initial):
            for node_output in event.values():
                if "final_answer" in node_output and node_output["final_answer"]:
                    yield node_output["final_answer"]

    async def astream_events(
        self,
        user_message: str,
        context: Dict[str, Any] | None = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield structured UI events during graph execution.

        Event types:
            plan_created      -- {"type": "plan_created", "plan": TaskPlan}
            step_started      -- {"type": "step_started", "step": str, "index": int}
            tool_call_started -- {"type": "tool_call_started", "name": str, "args": dict}
            tool_call_completed -- {"type": "tool_call_completed", "name": str, "result": str}
            thinking          -- {"type": "thinking", "thought": str}
            text_chunk        -- {"type": "text_chunk", "text": str}
            reflection        -- {"type": "reflection", "text": str}
            final_answer      -- {"type": "final_answer", "text": str}
        """
        from .state import TaskPlan

        await self.initialize()
        compiled = self._build_graph().compile()
        self.graph = compiled

        initial: dict[str, Any] = {
            "messages": [HumanMessage(content=user_message)],
            "final_answer": "",
        }
        if self.config.mode == NoeMode.ASK:
            initial["memory_context"] = []
        else:
            initial.update({"plan": None, "iteration": 0, "tool_results": [], "reflection": ""})

        _prev_plan_id: int | None = None
        _prev_tool_count = 0

        async for event in compiled.astream(initial):
            for node_name, node_output in event.items():
                if not isinstance(node_output, dict):
                    continue

                plan = node_output.get("plan")
                if plan is not None and isinstance(plan, TaskPlan):
                    plan_id = id(plan)
                    if plan_id != _prev_plan_id:
                        _prev_plan_id = plan_id
                        yield {"type": "plan_created", "plan": plan}
                    if plan.current_step:
                        yield {
                            "type": "step_started",
                            "step": plan.current_step.description,
                            "index": plan.current_step_index,
                        }

                tool_results = node_output.get("tool_results")
                if tool_results and isinstance(tool_results, list):
                    new_results = tool_results[_prev_tool_count:]
                    _prev_tool_count = len(tool_results)
                    for tr in new_results:
                        yield {
                            "type": "tool_call_completed",
                            "name": tr.get("tool", "?"),
                            "result": str(tr.get("result", ""))[:2000],
                        }

                msgs = node_output.get("messages")
                if msgs and isinstance(msgs, list):
                    for msg in msgs:
                        tc = getattr(msg, "tool_calls", None)
                        if tc:
                            for call in tc:
                                yield {
                                    "type": "tool_call_started",
                                    "name": call.get("name", "?"),
                                    "args": call.get("args", {}),
                                }
                        content = getattr(msg, "content", "")
                        if content and not tc:
                            sa = getattr(msg, "additional_kwargs", {}).get("subagent_action")
                            if sa:
                                yield {
                                    "type": "thinking",
                                    "thought": f"Delegating to subagent: {sa.get('name', '?')}",
                                }
                            else:
                                yield {"type": "text_chunk", "text": content}

                reflection = node_output.get("reflection")
                if reflection and isinstance(reflection, str):
                    yield {"type": "reflection", "text": reflection}

                final = node_output.get("final_answer")
                if final and isinstance(final, str):
                    yield {"type": "final_answer", "text": final}

    def run_tui(self) -> None:
        """Launch interactive Rich TUI loop."""
        from .tui import run_agent_tui

        run_agent_tui(self)

    # ------------------------------------------------------------------
    # Subagent API
    # ------------------------------------------------------------------

    async def spawn_subagent(self, name: str, *, mode: NoeMode = NoeMode.AGENT) -> str:
        if not self.config.enable_subagents:
            raise RuntimeError("Subagents are disabled in NoeConfig")
        if self._depth >= self.config.subagent_max_depth:
            raise RuntimeError("Subagent depth limit reached")

        child = NoeAgent(
            self.config.model_copy(
                update={
                    "mode": mode,
                    "memory_providers": ["working", "memu"],
                }
            )
        )
        child._depth = self._depth + 1
        subagent_id = f"{name}-{len(self._subagents) + 1}"
        self._subagents[subagent_id] = child
        return subagent_id

    async def interact_with_subagent(self, subagent_id: str, message: str) -> str:
        if subagent_id not in self._subagents:
            raise KeyError(f"Unknown subagent: {subagent_id}")
        return await self._subagents[subagent_id].arun(message)
