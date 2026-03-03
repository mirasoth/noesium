"""Graph node implementations for Noe (impl guide §4-5, RFC-1004)."""

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


def _build_tool_descriptions(registry: Any) -> str:
    """Format registry providers into a prompt-friendly description block."""
    if registry is None:
        return "No tools available."
    providers = registry.list_providers()
    if not providers:
        return "No tools available."
    lines: list[str] = []
    for p in providers:
        d = p.descriptor
        params = ""
        schema = d.input_schema or {}
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        if props:
            parts = []
            for pname, pinfo in props.items():
                req = " (required)" if pname in required else ""
                parts.append(f"    - {pname}: {pinfo.get('type', 'any')}{req}")
            params = "\n" + "\n".join(parts)
        desc = (d.description or "").split("\n")[0].strip()
        lines.append(f"- **{d.capability_id}**: {desc}{params}")
    return "\n".join(lines)


async def _persist_plan_to_memory(
    plan: TaskPlan | None,
    memory_manager: Any,
) -> None:
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
    registry: Any,
    memory_manager: Any = None,
    max_tool_calls: int = 5,
    tool_desc_cache: str | None = None,
) -> dict[str, Any]:
    """Execute current plan step via structured LLM output with tool access.

    Uses the unified ``CapabilityRegistry`` for tool descriptions.
    Accepts an optional ``tool_desc_cache`` to avoid regenerating
    the tool description string on every step (O4).
    """
    from langchain_core.messages import AIMessage

    plan: TaskPlan | None = state.get("plan")
    current_step = plan.current_step if plan else None
    step_desc = current_step.description if current_step else "Answer the question."
    hint = current_step.execution_hint if current_step else "auto"
    hint_text = {
        "tool": "Prefer using a tool for this step (atomic operation).",
        "subagent": "Consider delegating to a child agent for this step (multi-step reasoning).",
        "cli_subagent": "Consider delegating to an external CLI agent for this step.",
        "builtin_agent": "Consider delegating to a built-in specialized agent (browser_use, tacitus) for this step.",
        "auto": "Choose the best approach (tool, subagent, or direct answer).",
    }.get(hint, "Choose the best approach.")

    completed = "\n".join(f"- {r['tool']}: {str(r['result'])[:200]}" for r in state.get("tool_results", []))
    tool_desc = tool_desc_cache if tool_desc_cache is not None else _build_tool_descriptions(registry)

    system = AGENT_SYSTEM_PROMPT.format(
        plan=step_desc,
        execution_hint=hint_text,
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
        calls = action.tool_calls[:max_tool_calls]
        if len(action.tool_calls) > max_tool_calls:
            logger.warning(
                "LLM requested %d tool calls, truncating to %d",
                len(action.tool_calls),
                max_tool_calls,
            )
        tool_calls_data = [
            {
                "name": tc.tool_name,
                "args": tc.arguments,
                "id": f"call_{i}",
                "type": "tool_call",
            }
            for i, tc in enumerate(calls)
        ]
        msg = AIMessage(
            content=action.thought,
            tool_calls=tool_calls_data,
        )
        return {"messages": [msg]}

    if action.subagent:
        msg = AIMessage(
            content=action.thought,
            additional_kwargs={"subagent_action": action.subagent.model_dump()},
        )
        return {"messages": [msg]}

    return {"messages": [AIMessage(content=action.text_response or action.thought)]}


def _coerce_tool_args(args: dict[str, Any], descriptor: Any) -> dict[str, Any]:
    """Best-effort type coercion of tool arguments against the descriptor's input_schema."""
    schema = getattr(descriptor, "input_schema", None) or {}
    props = schema.get("properties", {})
    if not props:
        return args
    coerced = dict(args)
    for key, value in coerced.items():
        expected = props.get(key, {})
        expected_type = expected.get("type")
        if expected_type == "array" and isinstance(value, str):
            coerced[key] = [value]
        elif expected_type == "integer" and isinstance(value, str):
            try:
                coerced[key] = int(value)
            except ValueError:
                pass
        elif expected_type == "number" and isinstance(value, str):
            try:
                coerced[key] = float(value)
            except ValueError:
                pass
        elif expected_type == "boolean" and isinstance(value, str):
            coerced[key] = value.lower() in ("true", "1", "yes")
    return coerced


async def tool_node(
    state: AgentState,
    *,
    registry: Any,
    max_tool_calls: int = 5,
) -> dict[str, Any]:
    """Execute tool calls via CapabilityRegistry providers (direct invocation)."""
    from langchain_core.messages import ToolMessage

    last_msg = state["messages"][-1]
    tool_calls = getattr(last_msg, "tool_calls", None) or []
    results: list[dict[str, Any]] = []
    messages = []

    if len(tool_calls) > max_tool_calls:
        logger.warning(
            "Truncating tool calls from %d to %d (max_tool_calls_per_step)",
            len(tool_calls),
            max_tool_calls,
        )
        tool_calls = tool_calls[:max_tool_calls]

    for call in tool_calls:
        tool_name = call.get("name", "?")
        try:
            if tool_name == "subagent":
                args = call.get("args", {})
                redirect_name = "spawn_subagent"
                provider = registry.get_by_name(redirect_name)
                sa_args = {
                    "name": args.get("name", "subagent"),
                    "task": args.get("message", args.get("task", str(args))),
                    "mode": args.get("mode", "agent"),
                }
                result = await provider.invoke(**sa_args)
                results.append({"tool": f"subagent:{sa_args['name']}", "result": result})
                messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
                continue

            provider = registry.get_by_name(tool_name)
            coerced_args = _coerce_tool_args(call.get("args", {}), provider.descriptor)
            result = await provider.invoke(**coerced_args)
            results.append({"tool": tool_name, "result": result})
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
        except Exception as exc:
            logger.warning("Tool %s failed: %s", tool_name, exc)
            results.append({"tool": tool_name, "result": f"Error: {exc}"})
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
    """Handle subagent spawn/interact requests (in-process and CLI daemons)."""
    from langchain_core.messages import AIMessage

    last_msg = state["messages"][-1]
    sa_data = getattr(last_msg, "additional_kwargs", {}).get("subagent_action")
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
        elif sa.action == "interact":
            matching = [sid for sid in agent._subagents if sa.name in sid]
            if not matching:
                result = f"No subagent matching '{sa.name}' found."
            else:
                result = await agent.interact_with_subagent(matching[0], sa.message)
        elif sa.action == "spawn_cli":
            cli_adapter = getattr(agent, "_cli_adapter", None)
            if cli_adapter is None:
                result = "CLI subagent adapter not configured."
            else:
                result = await cli_adapter.spawn(sa.name, sa.message)
        elif sa.action == "interact_cli":
            cli_adapter = getattr(agent, "_cli_adapter", None)
            if cli_adapter is None:
                result = "CLI subagent adapter not configured."
            else:
                result = await cli_adapter.interact(sa.name, sa.message)
        elif sa.action == "terminate_cli":
            cli_adapter = getattr(agent, "_cli_adapter", None)
            if cli_adapter is None:
                result = "CLI subagent adapter not configured."
            else:
                result = await cli_adapter.terminate(sa.name)
        elif sa.action == "invoke_builtin":
            # Invoke a built-in specialized agent via the registry
            registry = getattr(agent, "_registry", None)
            if registry is None:
                result = "Capability registry not configured."
            else:
                try:
                    # Built-in agents are registered as "builtin_agent:{name}"
                    cap_id = f"builtin_agent:{sa.name}"
                    provider = registry.get_by_name(cap_id)
                    result = await provider.invoke(message=sa.message)
                except Exception as exc:
                    result = f"Failed to invoke built-in agent '{sa.name}': {exc}"
        elif sa.action == "invoke_cli":
            # Invoke CLI subagent (oneshot or daemon mode via unified interface)
            cli_adapter = getattr(agent, "_cli_adapter", None)
            if cli_adapter is None:
                result = "CLI subagent adapter not configured."
            else:
                # Build kwargs from SubagentAction options
                invoke_kwargs = {"message": sa.message}
                if sa.allowed_tools is not None:
                    invoke_kwargs["allowed_tools"] = sa.allowed_tools
                if sa.skip_permissions is not None:
                    invoke_kwargs["skip_permissions"] = sa.skip_permissions

                try:
                    # Try execute_oneshot first (preferred for CLI agents like Claude)
                    if hasattr(cli_adapter, "execute_oneshot"):
                        exec_result = await cli_adapter.execute_oneshot(sa.name, sa.message, **invoke_kwargs)
                        # Handle CliExecutionResult
                        if hasattr(exec_result, "success"):
                            result = exec_result.content if exec_result.success else f"Error: {exec_result.error}"
                        else:
                            result = str(exec_result)
                    else:
                        # Fallback to interact (daemon mode)
                        result = await cli_adapter.interact(sa.name, sa.message)
                except Exception as exc:
                    logger.warning("CLI invocation '%s' failed: %s", sa.name, exc)
                    result = f"Failed to invoke CLI agent '{sa.name}': {exc}"
        else:
            result = f"Unknown subagent action: {sa.action}"
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
