"""Graph node implementations for AlithiaAgent (impl guide §6)."""

from __future__ import annotations

import logging
from typing import Any

from noesium.core.memory.provider import RecallQuery, RecallScope

from .prompts import (
    AGENT_SYSTEM_PROMPT,
    ASK_SYSTEM_PROMPT,
    FINALIZE_PROMPT,
    REFLECTION_PROMPT,
)
from .state import AgentState, AskState, TaskPlan

logger = logging.getLogger(__name__)


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
) -> dict[str, Any]:
    """Use TaskPlanner to decompose the user's request."""
    user_msg = state["messages"][-1].content if state["messages"] else ""
    plan: TaskPlan = await planner.create_plan(user_msg)
    return {"plan": plan, "iteration": 0, "tool_results": [], "reflection": "", "final_answer": ""}


async def execute_step_node(
    state: AgentState,
    *,
    llm: Any,
    tool_names: list[str],
) -> dict[str, Any]:
    """Execute current plan step via LLM with tool access."""
    from langchain_core.messages import AIMessage

    plan: TaskPlan | None = state.get("plan")
    step_desc = plan.current_step.description if plan and plan.current_step else "Answer the question."
    completed = "\n".join(f"- {r['tool']}: {str(r['result'])[:200]}" for r in state.get("tool_results", []))
    system = AGENT_SYSTEM_PROMPT.format(
        plan=step_desc,
        completed_results=completed or "None yet.",
    )
    messages = [{"role": "system", "content": system}] + [
        {"role": m.type if hasattr(m, "type") else "user", "content": m.content} for m in state["messages"]
    ]
    response = llm.completion(messages=messages, temperature=0.2)
    return {"messages": [AIMessage(content=response)]}


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
            messages.append(ToolMessage(content=f"Error: {exc}", tool_call_id=call.get("id", "")))

    return {
        "tool_results": state.get("tool_results", []) + results,
        "messages": messages,
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
) -> dict[str, Any]:
    """Revise the plan based on reflection feedback."""
    plan: TaskPlan | None = state.get("plan")
    if plan is None:
        return {}
    completed = [str(r["result"])[:200] for r in state.get("tool_results", [])]
    new_plan = await planner.revise_plan(plan, state.get("reflection", ""), completed)
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
