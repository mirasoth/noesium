"""Graph construction for NoeAgent state machines."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:
    raise ImportError("Noe requires langgraph. Install it with: uv run pip install langgraph")

# Import state types at module level to ensure they're available in globals
# when LangGraph's get_type_hints() resolves type annotations in nested functions
from noeagent.state import AgentState, AskState

from . import nodes, routing

if TYPE_CHECKING:
    from noeagent.config import NoeConfig
    from noeagent.planner import TaskPlanner

    from noesium.core.capability.registry import CapabilityRegistry
    from noesium.core.memory.provider_manager import ProviderMemoryManager


def build_ask_graph(
    memory_manager: "ProviderMemoryManager | None",
    llm: Any,
    agent: Any = None,
) -> StateGraph:
    """Build Ask mode state graph.

    Args:
        memory_manager: Memory manager for context
        llm: LLM client for generation
        agent: NoeAgent instance (for live CognitiveContext access)

    Returns:
        Compiled StateGraph
    """
    _context = getattr(agent, "_context", None) if agent else None
    _config = getattr(agent, "config", None) if agent else None
    _max_export = getattr(_config, "context_max_export_tokens", None) if _config else None
    _history_turns = getattr(_config, "context_history_turns", 3) if _config else 3

    workflow = StateGraph(AskState)

    async def _recall(state: "AskState") -> dict:
        return await nodes.recall_memory_node(state, memory_manager=memory_manager)

    async def _answer(state: "AskState") -> dict:
        return await nodes.generate_answer_node(
            state,
            llm=llm,
            context=_context,
            max_export_tokens=_max_export,
            history_turns=_history_turns,
        )

    workflow.add_node("recall_memory", _recall)
    workflow.add_node("generate_answer", _answer)
    workflow.add_edge(START, "recall_memory")
    workflow.add_edge("recall_memory", "generate_answer")
    workflow.add_edge("generate_answer", END)
    return workflow


def build_agent_graph(
    planner: TaskPlanner | None,
    memory_manager: ProviderMemoryManager | None,
    registry: CapabilityRegistry | None,
    llm: Any,
    config: "NoeConfig",
    tool_desc_cache: str,
    agent: Any,  # NoeAgent instance for subagent spawning
) -> StateGraph:
    """Build Agent mode state graph.

    Args:
        planner: Task planner for decomposition
        memory_manager: Memory manager for context
        registry: Capability registry for tools
        llm: LLM client for reasoning
        config: Agent configuration
        tool_desc_cache: Cached tool descriptions
        agent: NoeAgent instance (for subagent spawning)

    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(AgentState)

    async def _plan(state: "AgentState") -> dict:
        return await nodes.plan_node(
            state,
            planner=planner,
            memory_manager=memory_manager,
        )

    _context = getattr(agent, "_context", None) if agent else None
    _max_export = getattr(config, "context_max_export_tokens", None)
    _history_turns = getattr(config, "context_history_turns", 3)

    async def _execute(state: "AgentState") -> dict:
        return await nodes.execute_step_node(
            state,
            llm=llm,
            registry=registry,
            memory_manager=memory_manager,
            max_tool_calls=config.max_tool_calls_per_step,
            tool_desc_cache=tool_desc_cache,
            context=_context,
            max_export_tokens=_max_export,
            history_turns=_history_turns,
        )

    async def _tools(state: "AgentState") -> dict:
        return await nodes.tool_node(
            state,
            registry=registry,
            max_tool_calls=config.max_tool_calls_per_step,
        )

    async def _subagent(state: "AgentState") -> dict:
        return await nodes.subagent_node(state, agent=agent)

    async def _reflect(state: "AgentState") -> dict:
        return await nodes.reflect_node(state, llm=llm)

    async def _revise(state: "AgentState") -> dict:
        return await nodes.revise_plan_node(
            state,
            planner=planner,
            memory_manager=memory_manager,
        )

    async def _finalize(state: "AgentState") -> dict:
        return await nodes.finalize_node(state, llm=llm)

    workflow.add_node("plan", _plan)
    workflow.add_node("execute_step", _execute)
    workflow.add_node("tool_node", _tools)
    workflow.add_node("subagent_node", _subagent)
    workflow.add_node("reflect", _reflect)
    workflow.add_node("revise_plan", _revise)
    workflow.add_node("finalize", _finalize)

    workflow.add_edge(START, "plan")
    workflow.add_edge("plan", "execute_step")

    # Create routing functions with bound config
    def _route_exec(state: "AgentState") -> str:
        return routing.route_after_execute(state, config)

    def _route_refl(state: "AgentState") -> str:
        return routing.route_after_reflect(state)

    workflow.add_conditional_edges(
        "execute_step",
        _route_exec,
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
        _route_refl,
        {
            "revise_plan": "revise_plan",
            "finalize": "finalize",
            "execute_step": "execute_step",
        },
    )
    workflow.add_edge("revise_plan", "execute_step")
    workflow.add_edge("finalize", END)
    return workflow
