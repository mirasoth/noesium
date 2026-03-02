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

from uuid_extensions import uuid7str

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
from .progress import ProgressEvent, ProgressEventType
from .state import AgentState, AskState

logger = logging.getLogger(__name__)


class NoeAgent(BaseGraphicAgent):
    """Long-running autonomous research assistant with structured tool calling."""

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
        self._cli_adapter: "ExternalCliAdapter | None" = None
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
            planning_llm = None
            if self.config.planning_model:
                from noesium.core.llm import get_llm_client

                try:
                    planning_llm = get_llm_client(
                        provider=self.config.llm_provider,
                        chat_model=self.config.planning_model,
                    )
                except Exception as exc:
                    logger.warning("Failed to create planning LLM, using default: %s", exc)
            cli_names = [c.name for c in self.config.cli_subagents]
            self._planner = TaskPlanner(
                self.llm,
                planning_llm=planning_llm,
                cli_subagent_names=cli_names,
            )
            await self._setup_cli_subagents()

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
        import os

        from noesium.core.toolify.base import AsyncBaseToolkit
        from noesium.core.toolify.config import ToolkitConfig
        from noesium.core.toolify.registry import ToolkitRegistry

        # Determine working directory for toolkits
        work_dir = self.config.working_directory or os.getcwd()

        for toolkit_name in self.config.enabled_toolkits:
            try:
                # Create toolkit config with working directory
                toolkit_config = ToolkitConfig(
                    name=toolkit_name,
                    config={
                        "workspace_root": work_dir,
                        "work_dir": work_dir,
                    },
                )
                toolkit = ToolkitRegistry.create_toolkit(toolkit_name, toolkit_config)
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

        if self.config.enable_subagents:
            self._register_subagent_tools()

    def _register_subagent_tools(self) -> None:
        """Register subagent spawn/interact as callable tools in the registry."""
        parent = self

        async def spawn_subagent(name: str, task: str, mode: str = "agent") -> str:
            """Spawn a child NoeAgent to work on a subtask autonomously and return its result.

            Args:
                name: Short identifier for the subagent (e.g. 'web-searcher', 'code-analyzer')
                task: The full task description to delegate to the child agent
                mode: 'agent' for full tool access, 'ask' for read-only Q&A
            """
            sid = await parent.spawn_subagent(name, mode=NoeMode(mode))
            return await parent.interact_with_subagent(sid, task)

        self._tool_registry.register(FunctionAdapter.from_function(spawn_subagent))

    async def _setup_cli_subagents(self) -> None:
        """Initialize ExternalCliAdapter if CLI subagents are configured."""
        if not self.config.cli_subagents:
            return
        from .cli_adapter import ExternalCliAdapter

        self._cli_adapter = ExternalCliAdapter()
        for cli_cfg in self.config.cli_subagents:
            try:
                result = await self._cli_adapter.spawn_from_config(cli_cfg)
                logger.info("CLI subagent setup: %s", result)
            except Exception as exc:
                logger.warning("Failed to spawn CLI subagent '%s': %s", cli_cfg.name, exc)

    async def _cleanup_subagents(self) -> None:
        """Terminate all in-process and CLI subagents."""
        self._subagents.clear()
        if self._cli_adapter is not None:
            await self._cli_adapter.terminate_all()

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
                max_tool_calls=self.config.max_tool_calls_per_step,
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
                max_tool_calls=self.config.max_tool_calls_per_step,
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
        if last_msg and getattr(last_msg, "additional_kwargs", {}).get("subagent_action"):
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
    # Progress helpers
    # ------------------------------------------------------------------

    def _make_session_id(self) -> str:
        return uuid7str()

    async def _fire_callbacks(self, event: ProgressEvent) -> None:
        """Invoke all registered progress callbacks, swallowing errors."""
        for cb in self.config.progress_callbacks:
            try:
                if hasattr(cb, "on_progress"):
                    await cb.on_progress(event)
                else:
                    await cb(event)
            except Exception as exc:
                logger.debug("Progress callback error: %s", exc)

    def _build_initial_state(self) -> dict[str, Any]:
        initial: dict[str, Any] = {
            "messages": [HumanMessage(content="")],
            "final_answer": "",
        }
        if self.config.mode == NoeMode.ASK:
            initial["memory_context"] = []
        else:
            initial.update({"plan": None, "iteration": 0, "tool_results": [], "reflection": ""})
        return initial

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
        """Async entry point.  Fires progress callbacks when registered."""
        final_answer = ""
        async for event in self.astream_progress(user_message, context):
            if event.type == ProgressEventType.FINAL_ANSWER:
                final_answer = event.text or ""

        if self.config.persist_memory and self._memory_manager and final_answer:
            await self._memory_manager.store(
                key=f"research:{user_message[:60]}",
                value=final_answer[:1000],
                content_type="research",
                tier=MemoryTier.PERSISTENT,
            )
        return final_answer

    async def stream(
        self,
        user_message: str,
        context: Dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming entry point -- yields final_answer text chunks only."""
        async for event in self.astream_progress(user_message, context):
            if event.type == ProgressEventType.FINAL_ANSWER and event.text:
                yield event.text

    async def astream_progress(
        self,
        user_message: str,
        context: Dict[str, Any] | None = None,
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Canonical typed progress stream (impl guide §5.5).

        Yields ``ProgressEvent`` objects covering the full agent lifecycle.
        Also fires all ``progress_callbacks`` registered in ``NoeConfig``.
        """
        from .state import TaskPlan

        await self.initialize()
        compiled = self._build_graph().compile()
        self.graph = compiled

        session_id = self._make_session_id()
        seq = 0

        def _next_seq() -> int:
            nonlocal seq
            seq += 1
            return seq

        def _evt(tp: ProgressEventType, **kw: Any) -> ProgressEvent:
            return ProgressEvent(type=tp, session_id=session_id, sequence=_next_seq(), **kw)

        async def _emit(evt: ProgressEvent) -> None:
            await self._fire_callbacks(evt)

        def _brief_args(args: dict[str, Any], max_len: int = 60) -> str:
            if not args:
                return ""
            parts = []
            for k, v in args.items():
                sv = str(v)
                if len(sv) > 40:
                    sv = sv[:37] + "..."
                parts.append(f'{k}="{sv}"' if isinstance(v, str) else f"{k}={sv}")
                if sum(len(p) for p in parts) > max_len:
                    break
            return ", ".join(parts)

        initial = self._build_initial_state()
        initial["messages"] = [HumanMessage(content=user_message)]

        start_evt = _evt(ProgressEventType.SESSION_START, summary=f"Session started: {user_message[:80]}")
        await _emit(start_evt)
        yield start_evt

        _prev_plan_id: int | None = None
        _prev_tool_count = 0
        _prev_step_index: int = -1

        try:
            async for raw_event in compiled.astream(initial):
                for node_name, node_output in raw_event.items():
                    if not isinstance(node_output, dict):
                        continue

                    # --- Plan created / revised ---
                    plan = node_output.get("plan")
                    if plan is not None and isinstance(plan, TaskPlan):
                        plan_id = id(plan)
                        if plan_id != _prev_plan_id:
                            is_revision = _prev_plan_id is not None
                            _prev_plan_id = plan_id
                            tp = ProgressEventType.PLAN_REVISED if is_revision else ProgressEventType.PLAN_CREATED
                            evt = _evt(
                                tp,
                                node=node_name,
                                summary=f"Plan: {plan.goal}",
                                detail=plan.to_todo_markdown(),
                                plan_snapshot=plan.model_dump(),
                            )
                            await _emit(evt)
                            yield evt

                        cur_idx = plan.current_step_index
                        if cur_idx > _prev_step_index and _prev_step_index >= 0:
                            for completed_idx in range(_prev_step_index, min(cur_idx, len(plan.steps))):
                                step = plan.steps[completed_idx]
                                if step.status == "completed":
                                    evt = _evt(
                                        ProgressEventType.STEP_COMPLETE,
                                        node=node_name,
                                        step_index=completed_idx,
                                        step_desc=step.description,
                                        summary=f"Completed step {completed_idx + 1}: {step.description}",
                                    )
                                    await _emit(evt)
                                    yield evt
                        _prev_step_index = cur_idx

                        if plan.current_step:
                            evt = _evt(
                                ProgressEventType.STEP_START,
                                node=node_name,
                                step_index=plan.current_step_index,
                                step_desc=plan.current_step.description,
                                summary=f"Step {plan.current_step_index + 1}/{len(plan.steps)}: {plan.current_step.description}",
                            )
                            await _emit(evt)
                            yield evt

                    # --- Tool results ---
                    tool_results = node_output.get("tool_results")
                    if tool_results and isinstance(tool_results, list):
                        new_results = tool_results[_prev_tool_count:]
                        _prev_tool_count = len(tool_results)
                        for tr in new_results:
                            tname = tr.get("tool", "?")
                            raw_result = str(tr.get("result", ""))
                            first_line = raw_result.split("\n", 1)[0].strip()[:120]
                            evt = _evt(
                                ProgressEventType.TOOL_END,
                                node=node_name,
                                tool_name=tname,
                                tool_result=first_line,
                                summary=f"{tname}: {first_line}" if first_line else f"{tname}: done",
                                detail=raw_result[:5000],
                            )
                            await _emit(evt)
                            yield evt

                    # --- Messages (tool calls, subagent delegation, text) ---
                    msgs = node_output.get("messages")
                    if msgs and isinstance(msgs, list):
                        for msg in msgs:
                            tc = getattr(msg, "tool_calls", None)
                            if tc:
                                for call in tc:
                                    cname = call.get("name", "?")
                                    cargs = call.get("args", {})
                                    brief_args = _brief_args(cargs)
                                    evt = _evt(
                                        ProgressEventType.TOOL_START,
                                        node=node_name,
                                        tool_name=cname,
                                        tool_args=cargs,
                                        summary=f"Using {cname}({brief_args})" if brief_args else f"Using {cname}",
                                        detail=str(cargs)[:2000],
                                    )
                                    await _emit(evt)
                                    yield evt
                            content = getattr(msg, "content", "")
                            if content and not tc:
                                sa = getattr(msg, "additional_kwargs", {}).get("subagent_action")
                                if sa:
                                    sa_name = sa.get("name", "?")
                                    sa_msg = sa.get("message", "")[:80]
                                    evt = _evt(
                                        ProgressEventType.SUBAGENT_START,
                                        node=node_name,
                                        subagent_id=sa_name,
                                        summary=f"[{sa_name}] {sa_msg}" if sa_msg else f"[{sa_name}] spawned",
                                        detail=str(sa),
                                    )
                                    await _emit(evt)
                                    yield evt
                                else:
                                    evt = _evt(
                                        ProgressEventType.TEXT_CHUNK,
                                        node=node_name,
                                        text=content,
                                        summary=content[:120],
                                    )
                                    await _emit(evt)
                                    yield evt

                    # --- Reflection ---
                    reflection = node_output.get("reflection")
                    if reflection and isinstance(reflection, str):
                        evt = _evt(
                            ProgressEventType.REFLECTION,
                            node=node_name,
                            text=reflection,
                            summary="Reflecting on progress",
                            detail=reflection,
                        )
                        await _emit(evt)
                        yield evt

                    # --- Final answer ---
                    final = node_output.get("final_answer")
                    if final and isinstance(final, str):
                        evt = _evt(
                            ProgressEventType.FINAL_ANSWER,
                            node=node_name,
                            text=final,
                            summary="Final answer ready",
                            detail=final,
                        )
                        await _emit(evt)
                        yield evt
        except Exception as exc:
            err_evt = _evt(
                ProgressEventType.ERROR,
                error=str(exc),
                summary=f"Error: {str(exc)[:100]}",
                detail=str(exc),
            )
            await _emit(err_evt)
            yield err_evt
            raise
        finally:
            await self._cleanup_subagents()
            end_evt = _evt(ProgressEventType.SESSION_END, summary="Session ended")
            await _emit(end_evt)
            yield end_evt

    async def astream_events(
        self,
        user_message: str,
        context: Dict[str, Any] | None = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Backward-compatible dict-based event stream.

        Wraps ``astream_progress()`` and converts each ``ProgressEvent`` to a
        plain dict.  New code should prefer ``astream_progress()`` directly.
        """
        async for event in self.astream_progress(user_message, context):
            yield event.model_dump()

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
