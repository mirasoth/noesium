"""Noe -- autonomous research assistant (impl guide §5, RFC-1004)."""

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
from noesium.core.capability.providers import (
    AgentCapabilityProvider,
    CliAgentCapabilityProvider,
    MCPCapabilityProvider,
    ToolCapabilityProvider,
)
from noesium.core.capability.registry import CapabilityRegistry
from noesium.core.event.envelope import AgentRef
from noesium.core.event.store import InMemoryEventStore
from noesium.core.library_consts import SUBAGENT_BROWSER_USE, SUBAGENT_TACITUS
from noesium.core.memory.provider import MemoryTier
from noesium.core.memory.provider_manager import ProviderMemoryManager
from noesium.core.memory.providers.event_sourced import EventSourcedProvider
from noesium.core.memory.providers.memu import MemuProvider
from noesium.core.memory.providers.working import WorkingMemoryProvider
from noesium.core.toolify.adapters.builtin_adapter import BuiltinAdapter
from noesium.core.toolify.adapters.function_adapter import FunctionAdapter
from noesium.core.toolify.atomic import ToolContext, ToolPermission
from noesium.core.toolify.executor import ToolExecutor

from . import nodes
from .config import _NOE_AGENT_CONSOLE_LOG_LEVEL, NoeConfig, NoeMode
from .planner import TaskPlanner
from .progress import ProgressEvent, ProgressEventType
from .state import AgentState, AskState

logger = logging.getLogger(__name__)


class NoeAgent(BaseGraphicAgent):
    """Long-running autonomous research assistant with structured tool calling.

    Uses the unified ``CapabilityRegistry`` (RFC-1004) as the single source of
    truth for all tools, MCP tools, skills, and subagent providers.
    """

    def __init__(self, config: NoeConfig | None = None) -> None:
        self.config = (config or NoeConfig()).effective()

        # Configure logging
        self._setup_logging()

        super().__init__(
            llm_provider=self.config.llm_provider,
            model_name=self.config.model_name,
        )
        self._agent_id = f"noe-{id(self)}"
        self._memory_manager: ProviderMemoryManager | None = None
        self._registry: CapabilityRegistry | None = None
        self._tool_executor: ToolExecutor | None = None
        self._tool_context: ToolContext | None = None
        self._planner: TaskPlanner | None = None
        self._planning_llm: Any = None
        self._cli_adapter: "ExternalCliAdapter | None" = None
        self._event_store = InMemoryEventStore()
        self._subagents: dict[str, "NoeAgent"] = {}
        self._depth: int = 0
        self._initialized: bool = False
        self._compiled_graph: Any = None
        self._compiled_mode: NoeMode | None = None
        self._tool_desc_cache: str | None = None
        self._tool_desc_provider_count: int = -1
        self._subagent_event_queue: asyncio.Queue[ProgressEvent] | None = None

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        await self._setup_memory()
        if self.config.mode == NoeMode.AGENT:
            await self._setup_capabilities()
            external_names = [c.name for c in self.config.external]
            enabled_builtin_subagents = self.config.get_enabled_builtin_subagents()
            builtin_names = [s.name for s in enabled_builtin_subagents]
            self._planner = TaskPlanner(
                self.llm,
                planning_llm=self._get_planning_llm(),
                external_subagent_names=external_names,
                builtin_subagent_names=builtin_names,
                builtin_subagent_configs=enabled_builtin_subagents,
            )
            await self._setup_external_subagents()
            await self._setup_builtin_subagents()
            # Warm up LLM connection to reduce first-query latency
            await self._warmup_llm()
        self._initialized = True

    async def reinitialize(self) -> None:
        """Force re-initialization after config changes (e.g. mode switch)."""
        self._initialized = False
        self._compiled_graph = None
        self._compiled_mode = None
        self._tool_desc_cache = None
        await self._cleanup_subagents()
        await self.initialize()

    def _get_planning_llm(self) -> Any:
        """Lazy creation of planning LLM client (O5)."""
        if self._planning_llm is not None:
            return self._planning_llm
        if not self.config.planning_model:
            return None
        from noesium.core.llm import get_llm_client

        try:
            self._planning_llm = get_llm_client(
                provider=self.config.llm_provider,
                chat_model=self.config.planning_model,
            )
        except Exception as exc:
            logger.warning("Failed to create planning LLM, using default: %s", exc)
        return self._planning_llm

    def _setup_logging(self) -> None:
        """Configure session-isolated logging.

        Console/TUI output is fixed at ERROR for UX simplicity.
        File-based logging goes to the session directory at a configurable level
        (default INFO), affecting noeagent, core, all subagents, and tools.
        """
        if hasattr(NoeAgent, "_logging_configured"):
            return

        session_dir = Path(self.config.session_dir)
        session_dir.mkdir(parents=True, exist_ok=True)

        from noesium.core.utils.logging import setup_logging

        setup_logging(
            console_level=_NOE_AGENT_CONSOLE_LOG_LEVEL,
            log_file=str(session_dir / "noeagent.log"),
            log_file_level=self.config.file_log_level,
            third_party_level=_NOE_AGENT_CONSOLE_LOG_LEVEL,
        )
        NoeAgent._logging_configured = True

    def _get_compiled_graph(self) -> Any:
        """Return cached compiled graph, rebuilding only on mode change (O1/O2)."""
        if self._compiled_graph is not None and self._compiled_mode == self.config.mode:
            return self._compiled_graph
        self._compiled_graph = self._build_graph().compile()
        self._compiled_mode = self.config.mode
        return self._compiled_graph

    def get_tool_descriptions(self) -> str:
        """Return cached tool description string, regenerating on registry change (O4)."""
        if self._registry is None:
            return "No tools available."
        provider_count = len(self._registry.list_providers())
        if self._tool_desc_cache is not None and self._tool_desc_provider_count == provider_count:
            return self._tool_desc_cache
        from .nodes import _build_tool_descriptions

        self._tool_desc_cache = _build_tool_descriptions(self._registry)
        self._tool_desc_provider_count = provider_count
        return self._tool_desc_cache

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

    async def _setup_capabilities(self) -> None:
        """Create CapabilityRegistry and register all providers (parallel toolkit loading)."""
        import os

        from noesium.core.toolify.base import AsyncBaseToolkit
        from noesium.core.toolify.config import ToolkitConfig
        from noesium.core.toolify.registry import ToolkitRegistry

        producer = AgentRef(agent_id=self._agent_id, agent_type="noe")

        self._tool_executor = ToolExecutor(
            event_store=self._event_store,
            producer=producer,
        )
        self._tool_context = ToolContext(
            agent_id=self._agent_id,
            granted_permissions=[ToolPermission(p) for p in self.config.permissions],
            working_directory=self.config.working_directory,
        )
        self._registry = CapabilityRegistry(
            event_store=self._event_store,
            producer=producer,
        )

        work_dir = self.config.working_directory or os.getcwd()
        session_dir = Path(self.config.session_dir)
        toolkit_session_base = session_dir / "toolkits"

        # Per-toolkit session-scoped directory overrides (under session_dir/toolkits/<name>/)
        _SESSION_DIR_OVERRIDES: dict[str, dict[str, str]] = {
            "document": {"cache_dir": "cache", "download_dir": "downloads"},
            "audio": {"cache_dir": "cache", "download_dir": "downloads"},
            "tabular_data": {"cache_dir": "cache"},
            "python_executor": {"default_workdir": "workdir"},
            "arxiv": {"default_download_dir": "papers"},
            "bash": {"workspace_root": "workspace"},
            "memory": {"storage_dir": "storage"},
            "file_edit": {"work_dir": "workspace"},
        }

        # Load toolkits in parallel for better performance
        async def _load_toolkit(toolkit_name: str) -> list:
            """Load a single toolkit and return its providers."""
            try:
                base_config: dict[str, Any] = {
                    "workspace_root": work_dir,
                    "work_dir": work_dir,
                }
                overrides = _SESSION_DIR_OVERRIDES.get(toolkit_name)
                if overrides:
                    toolkit_session_dir = toolkit_session_base / toolkit_name
                    for key, subdir in overrides.items():
                        base_config[key] = str(toolkit_session_dir / subdir)

                # Merge toolkit-specific config from self.config.toolkit_configs
                toolkit_specific_config = self.config.toolkit_configs.get(toolkit_name, {})
                base_config.update(toolkit_specific_config)

                toolkit_config = ToolkitConfig(
                    name=toolkit_name,
                    config=base_config,
                )
                toolkit = ToolkitRegistry.create_toolkit(toolkit_name, toolkit_config)
                if isinstance(toolkit, AsyncBaseToolkit):
                    await toolkit.build()
                tools = await BuiltinAdapter.from_toolkit(toolkit, toolkit_name)
                providers = []
                for tool in tools:
                    provider = ToolCapabilityProvider(tool, self._tool_executor, self._tool_context)
                    providers.append(provider)
                return providers
            except Exception as exc:
                logger.warning("Failed to load toolkit %s: %s", toolkit_name, exc)
                return []

        # Load all toolkits concurrently
        if self.config.enabled_toolkits:
            toolkit_tasks = [_load_toolkit(name) for name in self.config.enabled_toolkits]
            toolkit_results = await asyncio.gather(*toolkit_tasks, return_exceptions=True)

            # Register all providers from successfully loaded toolkits
            for result in toolkit_results:
                if isinstance(result, list):
                    for provider in result:
                        self._registry.register(provider)
                # Exceptions are already logged in _load_toolkit

        # MCP servers are disabled by default (mcp_servers defaults to empty list)
        # Only load if explicitly configured
        if self.config.mcp_servers:
            logger.info("Loading %d MCP server(s)...", len(self.config.mcp_servers))
            for mcp_config in self.config.mcp_servers:
                try:
                    session = await self._connect_mcp(mcp_config)
                    from noesium.core.toolify.adapters.mcp_adapter import MCPAdapter

                    adapter = MCPAdapter(session)
                    mcp_tools = await adapter.discover_tools()
                    for tool in mcp_tools:
                        provider = MCPCapabilityProvider(tool, self._tool_executor, self._tool_context)
                        self._registry.register(provider)
                except Exception as exc:
                    logger.warning("Failed to load MCP server: %s", exc)

        for func in self.config.custom_tools:
            tool = FunctionAdapter.from_function(func)
            provider = ToolCapabilityProvider(tool, self._tool_executor, self._tool_context)
            self._registry.register(provider)

        if self.config.enable_subagents:
            self._register_subagent_tool()

    def _register_subagent_tool(self) -> None:
        """Register subagent spawn as a callable tool provider."""
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

        tool = FunctionAdapter.from_function(spawn_subagent)
        provider = ToolCapabilityProvider(tool, self._tool_executor, self._tool_context)
        self._registry.register(provider)

    async def _setup_external_subagents(self) -> None:
        if not self.config.external:
            return
        from .cli_adapter import ExternalCliAdapter

        self._cli_adapter = ExternalCliAdapter()
        for cli_cfg in self.config.external:
            try:
                # Register config and setup provider (supports both oneshot and daemon modes)
                result = await self._cli_adapter.spawn_from_config(cli_cfg)
                provider = CliAgentCapabilityProvider(
                    cli_cfg.name,
                    self._cli_adapter,
                    task_types=cli_cfg.task_types,
                    mode=cli_cfg.mode,
                )
                self._registry.register(provider)
                logger.info("CLI subagent '%s' registered (mode=%s): %s", cli_cfg.name, cli_cfg.mode, result)
            except Exception as exc:
                logger.warning("Failed to setup CLI subagent '%s': %s", cli_cfg.name, exc)

    async def _setup_builtin_subagents(self) -> None:
        """Set up built-in agent subagents (browser_use, tacitus, etc.).

        This method registers built-in subagents from the config.builtin
        list as capability providers in the registry, making them available
        for the NoeAgent to invoke during task execution.
        """
        from noesium.core.capability.providers import BuiltInAgentCapabilityProvider

        enabled_subagents = self.config.get_enabled_builtin_subagents()
        if not enabled_subagents:
            return

        # Map agent_type to factory method
        agent_factories = {
            SUBAGENT_BROWSER_USE: self._create_browser_use_agent,
            SUBAGENT_TACITUS: self._create_tacitus_agent,
        }

        for subagent_cfg in enabled_subagents:
            factory_callable = agent_factories.get(subagent_cfg.agent_type)
            if factory_callable is None:
                logger.warning(
                    "Unknown agent type '%s' for subagent '%s'",
                    subagent_cfg.agent_type,
                    subagent_cfg.name,
                )
                continue

            # Bind subagent config so the factory receives it when invoked (no args)
            def make_factory(cfg: Any, factory_fn: Any) -> Any:
                def factory() -> Any:
                    return factory_fn(cfg)

                return factory

            try:
                provider = BuiltInAgentCapabilityProvider(
                    name=subagent_cfg.name,
                    agent_factory=make_factory(subagent_cfg, factory_callable),
                    agent_type=subagent_cfg.agent_type,
                    description=subagent_cfg.description or f"Built-in {subagent_cfg.agent_type} subagent",
                    task_types=subagent_cfg.task_types,
                )
                self._registry.register(provider)
                logger.info(
                    "Registered built-in subagent: %s (type=%s, tasks=%s)",
                    subagent_cfg.name,
                    subagent_cfg.agent_type,
                    subagent_cfg.task_types,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to register built-in subagent '%s': %s",
                    subagent_cfg.name,
                    exc,
                )

    async def _warmup_llm(self) -> None:
        """Send lightweight request to pre-load LLM model and warm connection.

        Non-blocking, non-fatal - logs warning on failure.
        This reduces the 71-second first-call latency by pre-loading the model
        during initialization rather than waiting for the first user query.
        """
        if not self.config.llm_warmup_on_init:
            return

        try:
            logger.info("Warming up LLM connection...")
            await asyncio.wait_for(
                asyncio.to_thread(self.llm.completion, [{"role": "user", "content": "Ready"}]),
                timeout=self.config.llm_warmup_timeout,
            )
            logger.info("LLM warm-up complete")
        except asyncio.TimeoutError:
            logger.warning(f"LLM warm-up timed out after {self.config.llm_warmup_timeout}s")
        except Exception as e:
            logger.warning(f"LLM warm-up failed (non-fatal): {e}")

    def _create_browser_use_agent(self, subagent_cfg: Any) -> Any:
        """Factory method to create a BrowserUseAgent instance.

        Args:
            subagent_cfg: Built-in subagent config (AgentSubagentConfig); may contain
                config.headless for headless/headed browser mode.

        Returns:
            BrowserUseAgent instance configured with the parent's LLM client,
            session directory, and optional headless from config.
        """
        try:
            from noesium.subagents.bu import BrowserUseAgent

            opts = (subagent_cfg.config or {}).copy()
            headless = opts.pop("headless", True)

            return BrowserUseAgent(
                llm=self.llm,
                parent_session_dir=self.config.session_dir,
                headless=headless,
            )
        except ImportError as exc:
            logger.error("Failed to import BrowserUseAgent: %s", exc)
            raise RuntimeError(f"BrowserUseAgent not available: {exc}") from exc

    def _create_tacitus_agent(self, subagent_cfg: Any = None) -> Any:
        """Factory method to create a TacitusAgent instance.

        Args:
            subagent_cfg: Built-in subagent config (optional; reserved for future options).

        Returns:
            TacitusAgent instance configured with the parent's LLM provider.
        """
        try:
            from noesium.subagents.tacitus import TacitusAgent

            return TacitusAgent(llm_provider=self.config.llm_provider)
        except ImportError as exc:
            logger.error("Failed to import TacitusAgent: %s", exc)
            raise RuntimeError(f"TacitusAgent not available: {exc}") from exc

    async def _cleanup_subagents(self) -> None:
        self._subagents.clear()
        if self._cli_adapter is not None:
            await self._cli_adapter.terminate_all()
        if self._registry is not None:
            await self._registry.stop_health_monitor()

    @staticmethod
    async def _connect_mcp(mcp_config: dict) -> Any:
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
                registry=self._registry,
                memory_manager=self._memory_manager,
                max_tool_calls=self.config.max_tool_calls_per_step,
                tool_desc_cache=self.get_tool_descriptions(),
            )

        async def _tools(state: AgentState) -> dict:
            return await nodes.tool_node(
                state,
                registry=self._registry,
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
        async for event in self.astream_progress(user_message, context):
            if event.type == ProgressEventType.FINAL_ANSWER and event.text:
                yield event.text

    async def astream_progress(
        self,
        user_message: str,
        context: Dict[str, Any] | None = None,
        *,
        subagent_name: str | None = None,
        subagent_names: list[str] | None = None,
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Canonical typed progress stream (impl guide §5.5).

        Subagents are specified explicitly (no slash parsing). Pass one or more
        subagent names; the same message is sent to each in sequence.

        - **subagent_names**: List of technical names (e.g. ``["browser_use", "tacitus"]``).
          The task is run by each subagent in order; all progress events are yielded.
        - **subagent_name**: Single subagent (converted to a one-element list internally).
        - If neither is set, the main graph runs (LLM routing, tools, etc.).
        """
        from .commands import inline_command_from_subagent
        from .state import TaskPlan

        await self.initialize()

        # Normalize to list: subagent_names takes precedence, then subagent_name
        names: list[str] = []
        if subagent_names:
            names = list(subagent_names)
        elif subagent_name is not None:
            names = [subagent_name]

        if names:
            logger.info(
                "Explicit subagent(s): %s <- %.80s",
                names,
                user_message,
            )
            for name in names:
                try:
                    inline_cmd = inline_command_from_subagent(name, user_message)
                except ValueError as e:
                    logger.warning("Skipping unknown subagent '%s': %s", name, e)
                    continue
                async for event in self._handle_inline_command(inline_cmd):
                    yield event
            return

        logger.debug(
            "Running main graph: %.80s",
            user_message,
        )
        compiled = self._get_compiled_graph()
        self.graph = compiled

        # O6: trim event store for long sessions to bound memory
        if hasattr(self._event_store, "_events") and len(self._event_store._events) > 10000:
            self._event_store._events = self._event_store._events[-5000:]

        # Callback-to-yield bridge: subagent events emitted inside nodes
        # are pushed to this queue so we can yield them from the generator.
        self._subagent_event_queue = asyncio.Queue()

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

        # Concurrent event merging: run LangGraph in a background task so that
        # subagent progress events are yielded in real-time while a node executes.
        # Previously, the queue was only drained *between* node executions, causing
        # tacitus/browser_use events to pile up and only appear after completion.
        _merged_q: asyncio.Queue = asyncio.Queue()
        _fwd_stop = object()  # sentinel to stop the forward task

        async def _run_graph() -> None:
            """Run LangGraph stream in background, forwarding raw events to _merged_q."""
            try:
                async for _raw in compiled.astream(initial):
                    await _merged_q.put(("graph", _raw))
            except Exception as _exc:
                await _merged_q.put(("error", _exc))
            finally:
                await _merged_q.put(("done", None))

        async def _forward_subagent_events() -> None:
            """Forward subagent events from _subagent_event_queue to _merged_q in real-time."""
            while True:
                _item = await self._subagent_event_queue.get()
                if _item is _fwd_stop:
                    break
                await _merged_q.put(("subagent", _item))

        _bg_graph = asyncio.create_task(_run_graph())
        _bg_fwd = asyncio.create_task(_forward_subagent_events())

        try:
            while True:
                _kind, _data = await _merged_q.get()
                if _kind == "done":
                    break
                elif _kind == "error":
                    raise _data
                elif _kind == "subagent":
                    yield _data
                    continue
                raw_event = _data  # _kind == "graph"

                for node_name, node_output in raw_event.items():
                    if not isinstance(node_output, dict):
                        continue

                    plan = node_output.get("plan")
                    if plan is not None and isinstance(plan, TaskPlan):
                        plan_id = id(plan)
                        if plan_id != _prev_plan_id:
                            is_revision = _prev_plan_id is not None
                            _prev_plan_id = plan_id
                            tp = ProgressEventType.PLAN_REVISED if is_revision else ProgressEventType.PLAN_CREATED
                            # Emit thinking event before plan
                            think_evt = _evt(
                                ProgressEventType.THINKING,
                                node=node_name,
                                summary=(
                                    "Analyzing task and creating plan..."
                                    if not is_revision
                                    else "Revising plan based on reflection..."
                                ),
                            )
                            await _emit(think_evt)
                            yield think_evt
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

                    msgs = node_output.get("messages")
                    if msgs and isinstance(msgs, list):
                        for msg in msgs:
                            tc = getattr(msg, "tool_calls", None)
                            if tc:
                                for call in tc:
                                    cname = call.get("name", "?")
                                    cargs = call.get("args", {})
                                    brief_args = _brief_args(cargs)
                                    # Emit thinking event for tool use
                                    think_evt = _evt(
                                        ProgressEventType.THINKING,
                                        node=node_name,
                                        summary=f"Deciding to use {cname}...",
                                    )
                                    await _emit(think_evt)
                                    yield think_evt
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

                    reflection = node_output.get("reflection")
                    if reflection and isinstance(reflection, str):
                        # Emit thinking event for reflection
                        think_evt = _evt(
                            ProgressEventType.THINKING,
                            node=node_name,
                            summary="Evaluating progress and results...",
                        )
                        await _emit(think_evt)
                        yield think_evt
                        evt = _evt(
                            ProgressEventType.REFLECTION,
                            node=node_name,
                            text=reflection,
                            summary="Reflecting on progress",
                            detail=reflection,
                        )
                        await _emit(evt)
                        yield evt

                    final = node_output.get("final_answer")
                    if final and isinstance(final, str):
                        # Emit thinking event for finalizing
                        think_evt = _evt(
                            ProgressEventType.THINKING,
                            node=node_name,
                            summary="Synthesizing final answer...",
                        )
                        await _emit(think_evt)
                        yield think_evt
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
            # Stop background tasks
            _bg_graph.cancel()
            # Signal the forward task to stop and wait for it
            await self._subagent_event_queue.put(_fwd_stop)
            try:
                await asyncio.gather(_bg_fwd, return_exceptions=True)
            except Exception:
                pass
            # Drain any remaining subagent events from the merged queue
            while not _merged_q.empty():
                try:
                    _k, _d = _merged_q.get_nowait()
                    if _k == "subagent":
                        yield _d
                except asyncio.QueueEmpty:
                    break
            self._subagent_event_queue = None
            await self._cleanup_subagents()
            end_evt = _evt(ProgressEventType.SESSION_END, summary="Session ended")
            await _emit(end_evt)
            yield end_evt

    async def astream_events(
        self,
        user_message: str,
        context: Dict[str, Any] | None = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Backward-compatible dict-based event stream."""
        async for event in self.astream_progress(user_message, context):
            yield event.model_dump()

    def run_tui(self) -> None:
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

        # O2: share parent's toolkit infrastructure to avoid re-loading
        if self._registry is not None:
            child._registry = self._registry
            child._tool_executor = self._tool_executor
            child._tool_context = ToolContext(
                agent_id=f"{self._agent_id}:{name}",
                granted_permissions=(self._tool_context.granted_permissions if self._tool_context else []),
                working_directory=(self._tool_context.working_directory if self._tool_context else None),
            )

        subagent_id = f"{name}-{len(self._subagents) + 1}"
        self._subagents[subagent_id] = child

        if self._registry is not None:
            provider = AgentCapabilityProvider(subagent_id, child)
            self._registry.register(provider)

        return subagent_id

    async def interact_with_subagent(self, subagent_id: str, message: str) -> str:
        """Stream child agent progress, forwarding events to parent callbacks and queue."""
        if subagent_id not in self._subagents:
            raise KeyError(f"Unknown subagent: {subagent_id}")

        child = self._subagents[subagent_id]
        final_answer = ""

        async for event in child.astream_progress(message):
            if event.type == ProgressEventType.FINAL_ANSWER:
                final_answer = event.text or ""
            elif event.type not in (
                ProgressEventType.SESSION_START,
                ProgressEventType.SESSION_END,
            ):
                wrapped = ProgressEvent(
                    type=ProgressEventType.SUBAGENT_PROGRESS,
                    session_id=event.session_id,
                    sequence=event.sequence,
                    subagent_id=subagent_id,
                    summary=f"[{subagent_id}] {event.summary or ''}",
                    detail=event.detail,
                    tool_name=event.tool_name,
                    step_index=event.step_index,
                    step_desc=event.step_desc,
                    plan_snapshot=event.plan_snapshot,
                    metadata={
                        "child_event_type": event.type.value,
                        "child_node": event.node,
                        **event.metadata,
                    },
                )
                await self._fire_callbacks(wrapped)
                if self._subagent_event_queue is not None:
                    self._subagent_event_queue.put_nowait(wrapped)

        end_event = ProgressEvent(
            type=ProgressEventType.SUBAGENT_END,
            subagent_id=subagent_id,
            summary=f"[{subagent_id}] completed",
        )
        await self._fire_callbacks(end_event)
        if self._subagent_event_queue is not None:
            self._subagent_event_queue.put_nowait(end_event)

        return final_answer

    async def interact_with_subagents(self, requests: list[tuple[str, str]]) -> dict[str, str]:
        """Execute multiple subagent interactions in parallel (O3)."""
        tasks = [self.interact_with_subagent(sid, msg) for sid, msg in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {sid: (r if isinstance(r, str) else f"Error: {r}") for (sid, _), r in zip(requests, results)}

    async def execute_builtin_subagent_streaming(
        self,
        provider: Any,
        message: str,
        subagent_name: str,
    ) -> str:
        """Execute a built-in subagent with progress streaming to TUI.

        This method streams progress events from the built-in subagent,
        forwarding them to parent callbacks and queuing them for
        astream_progress() to yield to the TUI.

        Args:
            provider: The BuiltInAgentCapabilityProvider instance.
            message: The task message for the subagent.
            subagent_name: Name of the subagent for event tagging.

        Returns:
            The final result string from the subagent.
        """
        final_result = ""

        async for event in provider.invoke_streaming(message=message):
            # Fire to callbacks (SessionLogger, etc.)
            await self._fire_callbacks(event)

            # Queue for astream_progress to yield
            if self._subagent_event_queue is not None:
                self._subagent_event_queue.put_nowait(event)

            # Track final result
            if event.type == ProgressEventType.SUBAGENT_END:
                final_result = event.detail or event.summary or ""

        return final_result

    async def _handle_inline_command(
        self,
        command: "InlineCommand",
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Handle explicit subagent invocation and yield progress events.

        Invokes the subagent specified in the command (e.g. browser_use, tacitus)
        without LLM routing. The command is built via inline_command_from_subagent.

        Args:
            command: Parsed inline command with subagent_name and message.

        Yields:
            ProgressEvent objects for session tracking and UI display.
        """
        from uuid_extensions import uuid7str

        from .commands import get_subagent_display_name

        session_id = uuid7str()
        seq = 0

        def _next_seq() -> int:
            nonlocal seq
            seq += 1
            return seq

        def _evt(tp: ProgressEventType, **kw: Any) -> ProgressEvent:
            return ProgressEvent(type=tp, session_id=session_id, sequence=_next_seq(), **kw)

        subagent_name = command.subagent_name
        message = command.message
        display_name = get_subagent_display_name(subagent_name)

        # Emit session start
        start_evt = _evt(
            ProgressEventType.SESSION_START,
            summary=f"Command: /{command.command_type.value} {message[:60]}",
        )
        await self._fire_callbacks(start_evt)
        yield start_evt

        if not message:
            error_evt = _evt(
                ProgressEventType.ERROR,
                error=f"No task provided for {display_name}. Usage: /{command.command_type.value} <your task>",
            )
            await self._fire_callbacks(error_evt)
            yield error_evt
            end_evt = _evt(ProgressEventType.SESSION_END, summary="Session ended (error)")
            await self._fire_callbacks(end_evt)
            yield end_evt
            return

        # Emit subagent start
        sa_start_evt = _evt(
            ProgressEventType.SUBAGENT_START,
            subagent_id=subagent_name,
            summary=f"[{display_name}] {message[:60]}",
        )
        await self._fire_callbacks(sa_start_evt)
        yield sa_start_evt

        # Try to find the subagent in the registry
        registry = self._registry
        if registry is None:
            error_evt = _evt(
                ProgressEventType.ERROR,
                error="Agent not properly initialized (no capability registry)",
            )
            await self._fire_callbacks(error_evt)
            yield error_evt
            end_evt = _evt(ProgressEventType.SESSION_END, summary="Session ended (error)")
            await self._fire_callbacks(end_evt)
            yield end_evt
            return

        # Check if it's a built-in subagent
        cap_id = f"builtin_agent:{subagent_name}"
        try:
            provider = registry.get_by_name(cap_id)
        except Exception:
            provider = None

        if provider is None:
            # Check if the subagent is configured but not enabled
            enabled_subagents = self.config.get_enabled_builtin_subagents()
            subagent_types = [s.agent_type for s in enabled_subagents]
            if subagent_name not in subagent_types:
                error_msg = f"Subagent '{display_name}' is not enabled. Enable it in your config."
            else:
                error_msg = f"Subagent '{display_name}' not found in registry."

            error_evt = _evt(ProgressEventType.ERROR, error=error_msg)
            await self._fire_callbacks(error_evt)
            yield error_evt

            sa_end_evt = _evt(
                ProgressEventType.SUBAGENT_END,
                subagent_id=subagent_name,
                summary=f"[{display_name}] failed",
            )
            await self._fire_callbacks(sa_end_evt)
            yield sa_end_evt

            end_evt = _evt(ProgressEventType.SESSION_END, summary="Session ended (error)")
            await self._fire_callbacks(end_evt)
            yield end_evt
            return

        # Execute the subagent
        final_result = ""
        try:
            if hasattr(provider, "invoke_streaming"):
                # Stream progress events from the subagent
                async for event in provider.invoke_streaming(message=message):
                    # Tag events with subagent info and forward
                    if event.subagent_id is None:
                        event = ProgressEvent(**{**event.model_dump(), "subagent_id": subagent_name})
                    await self._fire_callbacks(event)
                    yield event

                    if event.type == ProgressEventType.SUBAGENT_END:
                        final_result = event.detail or event.summary or ""
                    elif event.type == ProgressEventType.FINAL_ANSWER:
                        final_result = event.text or ""
            else:
                # Non-streaming invocation
                result = await provider.invoke(message=message)
                final_result = str(result)

                # Emit end event with result
                sa_end_evt = _evt(
                    ProgressEventType.SUBAGENT_END,
                    subagent_id=subagent_name,
                    summary=f"[{display_name}] completed",
                    detail=final_result,
                )
                await self._fire_callbacks(sa_end_evt)
                yield sa_end_evt
        except Exception as exc:
            logger.warning("Subagent '%s' execution failed: %s", subagent_name, exc)
            error_evt = _evt(
                ProgressEventType.ERROR,
                error=f"Error executing {display_name}: {exc}",
            )
            await self._fire_callbacks(error_evt)
            yield error_evt

            sa_end_evt = _evt(
                ProgressEventType.SUBAGENT_END,
                subagent_id=subagent_name,
                summary=f"[{display_name}] failed",
            )
            await self._fire_callbacks(sa_end_evt)
            yield sa_end_evt

            end_evt = _evt(ProgressEventType.SESSION_END, summary="Session ended (error)")
            await self._fire_callbacks(end_evt)
            yield end_evt
            return

        # Emit final answer if we have a result
        if final_result:
            final_evt = _evt(
                ProgressEventType.FINAL_ANSWER,
                text=final_result,
                summary="Final answer ready",
                detail=final_result,
            )
            await self._fire_callbacks(final_evt)
            yield final_evt

        # Emit session end
        end_evt = _evt(ProgressEventType.SESSION_END, summary="Session ended")
        await self._fire_callbacks(end_evt)
        yield end_evt
