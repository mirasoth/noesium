"""Graph node implementations for Noe (impl guide §4-5)."""

from __future__ import annotations

import logging
from typing import Any

from noesium.core.memory.provider import MemoryTier, RecallQuery, RecallScope

from .prompts import (
    AGENT_SYSTEM_PROMPT,
    ASK_SYSTEM_PROMPT,
    FINALIZE_PROMPT,
    REFLECTION_PROMPT,
)
from .schemas import AgentAction
from .state import AgentState, AskState, TaskPlan

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_tool_descriptions(tool_registry: Any) -> str:
    """Format tool registry entries into a prompt-friendly description block."""
    if tool_registry is None:
        return "No tools available."
    tools = tool_registry.list_tools()
    if not tools:
        return "No tools available."
    lines: list[str] = []
    for t in tools:
        params = ""
        schema = t.input_schema or {}
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        if props:
            parts = []
            for pname, pinfo in props.items():
                req = " (required)" if pname in required else ""
                parts.append(f"    - {pname}: {pinfo.get('type', 'any')}{req}")
            params = "\n" + "\n".join(parts)
        desc = (t.description or "").split("\n")[0].strip()
        lines.append(f"- **{t.name}**: {desc}{params}")
    return "\n".join(lines)


async def _persist_plan_to_memory(
    plan: TaskPlan | None,
    memory_manager: Any,
) -> None:
    """Write current plan as todo markdown into working memory."""
    if plan is None or memory_manager is None:
        return
    try:
        await memory_manager.store(
            key="current_plan",
            value=plan.to_todo_markdown(),
            content_type="plan",
            tier=MemoryTier.WORKING,
        )
    except Exception as exc:
        logger.debug("Failed to persist plan to memory: %s", exc)


# ---------------------------------------------------------------------------
# Ask-mode nodes
# ---------------------------------------------------------------------------


async def recall_memory_node(
    state: AskState,
    *,
    memory_manager: Any,
) -> dict[str, Any]:
    """Query MemoryManager with the user's question across all providers."""
    user_msg = state["messages"][-1].content if state["messages"] else ""
    context: list[dict[str, Any]] = []
    if memory_manager is not None:
        try:
            query = RecallQuery(query=user_msg, scope=RecallScope.ALL, limit=10)
            results = await memory_manager.recall(query)
            context = [{"key": r.entry.key, "value": r.entry.value, "score": r.score} for r in results]
        except Exception as exc:
            logger.warning("Memory recall failed: %s", exc)
    return {"memory_context": context}


async def generate_answer_node(
    state: AskState,
    *,
    llm: Any,
) -> dict[str, Any]:
    """Generate answer using LLM with memory context. No tool calls."""
    mem_ctx = state.get("memory_context") or []
    mem_text = "\n".join(f"- {m['key']}: {m['value']}" for m in mem_ctx) or "No memory context."
    system = ASK_SYSTEM_PROMPT.format(memory_context=mem_text)
    user_msg = state["messages"][-1].content if state["messages"] else ""
    answer = llm.completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
    )
    return {"final_answer": answer}


# ---------------------------------------------------------------------------
# Agent-mode nodes
# ---------------------------------------------------------------------------


async def plan_node(
    state: AgentState,
    *,
    planner: Any,
    memory_manager: Any = None,
) -> dict[str, Any]:
    """Use TaskPlanner to decompose the user's request."""
    user_msg = state["messages"][-1].content if state["messages"] else ""
    plan: TaskPlan = await planner.create_plan(user_msg)
    await _persist_plan_to_memory(plan, memory_manager)
    return {
        "plan": plan,
        "iteration": 0,
        "tool_results": [],
        "reflection": "",
        "final_answer": "",
    }


async def execute_step_node(
    state: AgentState,
    *,
    llm: Any,
    tool_registry: Any,
    memory_manager: Any = None,
) -> dict[str, Any]:
    """Execute current plan step via structured LLM output with tool access.

    Uses ``structured_completion`` to get an ``AgentAction`` that may contain
    tool calls, a subagent request, or a direct text response.
    """
    from langchain_core.messages import AIMessage

    plan: TaskPlan | None = state.get("plan")
    step_desc = plan.current_step.description if plan and plan.current_step else "Answer the question."
    completed = "\n".join(f"- {r['tool']}: {str(r['result'])[:200]}" for r in state.get("tool_results", []))
    tool_desc = _build_tool_descriptions(tool_registry)

    system = AGENT_SYSTEM_PROMPT.format(
        plan=step_desc,
        completed_results=completed or "None yet.",
        tool_descriptions=tool_desc,
    )
    user_msg = state["messages"][-1].content if state["messages"] else ""

    try:
        action: AgentAction = llm.structured_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            response_model=AgentAction,
            temperature=0.2,
        )
    except Exception as exc:
        logger.warning("Structured completion failed, falling back to text: %s", exc)
        text = llm.completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
        )
        return {"messages": [AIMessage(content=str(text))]}

    if action.mark_step_complete and plan:
        plan.advance()
        await _persist_plan_to_memory(plan, memory_manager)

    if action.tool_calls:
        tool_calls_data = [
            {
                "name": tc.tool_name,
                "args": tc.arguments,
                "id": f"call_{i}",
                "type": "tool_call",
            }
            for i, tc in enumerate(action.tool_calls)
        ]
        msg = AIMessage(
            content=action.thought,
            tool_calls=tool_calls_data,
        )
        return {"messages": [msg]}

    if action.subagent:
        msg = AIMessage(content=action.thought)
        msg.additional_kwargs["subagent_action"] = action.subagent.model_dump()
        return {"messages": [msg]}

    return {"messages": [AIMessage(content=action.text_response or action.thought)]}


async def tool_node(
    state: AgentState,
    *,
    tool_registry: Any,
    tool_executor: Any,
    context: Any,
) -> dict[str, Any]:
    """Execute tool calls via ToolExecutor."""
    from langchain_core.messages import ToolMessage

    last_msg = state["messages"][-1]
    tool_calls = getattr(last_msg, "tool_calls", None) or []
    results: list[dict[str, Any]] = []
    messages = []

    for call in tool_calls:
        try:
            tool = tool_registry.get_by_name(call["name"])
            result = await tool_executor.run(tool, context, **call["args"])
            results.append({"tool": call["name"], "result": result})
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
        except Exception as exc:
            logger.warning("Tool %s failed: %s", call.get("name", "?"), exc)
            results.append({"tool": call.get("name", "?"), "result": f"Error: {exc}"})
            messages.append(
                ToolMessage(
                    content=f"Error: {exc}",
                    tool_call_id=call.get("id", ""),
                )
            )

    return {
        "tool_results": state.get("tool_results", []) + results,
        "messages": messages,
        "iteration": state["iteration"] + 1,
    }


async def subagent_node(
    state: AgentState,
    *,
    agent: Any,
) -> dict[str, Any]:
    """Handle subagent spawn/interact requests."""
    from langchain_core.messages import AIMessage

    last_msg = state["messages"][-1]
    sa_data = last_msg.additional_kwargs.get("subagent_action")
    if not sa_data:
        return {"messages": [AIMessage(content="No subagent action found.")]}

    from .schemas import SubagentAction

    sa = SubagentAction(**sa_data)
    try:
        if sa.action == "spawn":
            from .config import NoeMode

            mode = NoeMode(sa.mode) if sa.mode in ("ask", "agent") else NoeMode.AGENT
            subagent_id = await agent.spawn_subagent(sa.name, mode=mode)
            if sa.message:
                result = await agent.interact_with_subagent(subagent_id, sa.message)
            else:
                result = f"Subagent '{subagent_id}' spawned successfully."
        else:
            matching = [sid for sid in agent._subagents if sa.name in sid]
            if not matching:
                result = f"No subagent matching '{sa.name}' found."
            else:
                result = await agent.interact_with_subagent(matching[0], sa.message)
    except Exception as exc:
        logger.warning("Subagent operation failed: %s", exc)
        result = f"Subagent error: {exc}"

    return {
        "tool_results": state.get("tool_results", []) + [{"tool": f"subagent:{sa.name}", "result": result}],
        "messages": [AIMessage(content=str(result))],
        "iteration": state["iteration"] + 1,
    }


async def reflect_node(
    state: AgentState,
    *,
    llm: Any,
) -> dict[str, Any]:
    """Reflect on progress and decide whether to revise the plan."""
    plan: TaskPlan | None = state.get("plan")
    goal = plan.goal if plan else ""
    plan_steps = ""
    if plan:
        plan_steps = "\n".join(f"  {i + 1}. [{s.status}] {s.description}" for i, s in enumerate(plan.steps))
    completed = "\n".join(f"- {r['tool']}: {str(r['result'])[:200]}" for r in state.get("tool_results", []))
    prompt = REFLECTION_PROMPT.format(
        goal=goal,
        plan_steps=plan_steps or "No plan.",
        completed_results=completed or "None.",
    )
    reflection = llm.completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return {"reflection": reflection}


async def revise_plan_node(
    state: AgentState,
    *,
    planner: Any,
    memory_manager: Any = None,
) -> dict[str, Any]:
    """Revise the plan based on reflection feedback."""
    plan: TaskPlan | None = state.get("plan")
    if plan is None:
        return {}
    completed = [str(r["result"])[:200] for r in state.get("tool_results", [])]
    new_plan = await planner.revise_plan(plan, state.get("reflection", ""), completed)
    await _persist_plan_to_memory(new_plan, memory_manager)
    return {"plan": new_plan}


async def finalize_node(
    state: AgentState,
    *,
    llm: Any,
) -> dict[str, Any]:
    """Generate the final comprehensive answer."""
    plan: TaskPlan | None = state.get("plan")
    goal = plan.goal if plan else ""
    results = "\n".join(f"- {r['tool']}: {str(r['result'])[:300]}" for r in state.get("tool_results", []))
    if not results:
        last_msg = state["messages"][-1].content if state["messages"] else ""
        results = last_msg

    prompt = FINALIZE_PROMPT.format(goal=goal, results=results)
    answer = llm.completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return {"final_answer": answer}
