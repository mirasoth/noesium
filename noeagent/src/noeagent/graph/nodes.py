"""Graph node implementations for Noe (impl guide §4-5, RFC-1004)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from noeagent.prompts import get_prompt_manager
from noeagent.schemas import AgentAction
from noeagent.state import AgentState, AskState, TaskPlan

from noesium.core.memory.provider import MemoryTier, RecallQuery, RecallScope

logger = logging.getLogger(__name__)


def _get_current_datetime() -> str:
    """Get the current datetime in explicit, prompt-friendly format.

    Returns:
        String like "Today's date: 2026-03-04. Current time (UTC): 14:30:00."
        so the agent can compare source dates and avoid treating future-dated
        results as current.
    """
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y-%m-%d")
    time_part = now.strftime("%H:%M:%S")
    return f"Today's date: {date_part}. Current time (UTC): {time_part}."


# ---------------------------------------------------------------------------
# Async Helper for Synchronous LLM Calls
# ---------------------------------------------------------------------------


def _is_content_filter_error(exc: Exception) -> bool:
    """Check if the exception is a content filtering/policy error (non-retryable)."""
    error_str = str(exc).lower()
    if "data_inspection_failed" in error_str:
        return True
    if "inappropriate content" in error_str:
        return True
    if "content_filter" in error_str:
        return True
    if "content_policy" in error_str:
        return True
    if "safety" in error_str and "violation" in error_str:
        return True
    return False


def _content_filter_error_message(exc: Exception) -> str:
    """Generate a user-friendly error message for content filter errors."""
    error_str = str(exc)
    # Try to identify the provider
    if "data_inspection_failed" in error_str.lower():
        provider = "Dashscope/Alibaba Cloud"
    elif "content_filter" in error_str.lower():
        provider = "OpenAI"
    else:
        provider = "the LLM provider"

    return (
        f"⚠️ Content Policy Violation\n\n"
        f"Your request was blocked by {provider}'s content safety system. "
        f"This can happen with sensitive topics like wars, conflicts, or other content "
        f"that may violate usage policies.\n\n"
        f"Suggestions:\n"
        f"• Rephrase your query in more neutral terms\n"
        f"• Try using a different LLM provider (e.g., switch from Dashscope to OpenAI)\n"
        f"• Use the research subagent (explicit selection) for web-based information gathering\n\n"
        f"Technical details: {error_str[:200]}"
    )


async def _run_llm_async(llm: Any, method: str, **kwargs: Any) -> Any:
    """Run a synchronous LLM method in a thread pool to avoid blocking.

    Args:
        llm: The LLM client instance
        method: Method name ('completion' or 'structured_completion')
        **kwargs: Arguments to pass to the method

    Returns:
        The result from the LLM call
    """
    func = getattr(llm, method)
    return await asyncio.get_event_loop().run_in_executor(None, lambda: func(**kwargs))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_tool_descriptions(registry: Any) -> str:
    """Format registry providers into a prompt-friendly description block.

    Uses display names for better readability (e.g., 'WebSearch' instead of 'web_search').
    """
    from noeagent.commands import get_toolkit_display_name

    if registry is None:
        return "No tools available."
    providers = registry.list_providers()
    if not providers:
        return "No tools available."
    lines: list[str] = []
    for p in providers:
        d = getattr(p, "descriptor", None)
        if not d:
            continue
        schema = getattr(d, "input_schema", None) or {}
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        params = ""
        if props:
            parts = []
            for pname, pinfo in props.items():
                req = " (required)" if pname in required else ""
                parts.append(f"    - {pname}: {pinfo.get('type', 'any')}{req}")
            params = "\n" + "\n".join(parts)
        desc = (getattr(d, "description", None) or "").split("\n")[0].strip()
        cap_id = getattr(d, "capability_id", "unknown")
        # Use display name if available
        # cap_id format is usually "toolkit:tool_name" or just "tool_name"
        if ":" in cap_id:
            toolkit_name, tool_name = cap_id.split(":", 1)
            display_name = get_toolkit_display_name(toolkit_name)
            display_cap_id = f"{display_name}:{tool_name}"
        else:
            display_cap_id = cap_id
        lines.append(f"- **{display_cap_id}**: {desc}{params}")
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
    mem_text = "\n".join(f"- {m.get('key', '')}: {m.get('value', '')}" for m in mem_ctx) or "No memory context."
    pm = get_prompt_manager()
    system = pm.render("ask_system", memory_context=mem_text, current_datetime=_get_current_datetime())
    user_msg = state["messages"][-1].content if state["messages"] else ""
    answer = await _run_llm_async(
        llm,
        "completion",
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
        "external_subagent": "Consider delegating to an external CLI agent (e.g., Claude) for this step.",
        "builtin_agent": "Consider delegating to a built-in specialized agent (browser_use, tacitus) for this step.",
        "auto": "Choose the best approach (tool, subagent, or direct answer).",
    }.get(hint, "Choose the best approach.")

    completed = "\n".join(
        f"- {r.get('tool', 'unknown')}: {str(r.get('result', ''))[:200]}" for r in state.get("tool_results", [])
    )
    tool_desc = tool_desc_cache if tool_desc_cache is not None else _build_tool_descriptions(registry)

    # RFC-1009: Include cognitive context summary if available
    context_summary = state.get("context_summary", "")
    context_block = f"\n\n## Context\n{context_summary}" if context_summary else ""

    pm = get_prompt_manager()
    system = pm.render(
        "agent_system",
        plan=step_desc,
        execution_hint=hint_text,
        completed_results=completed or "None yet.",
        tool_descriptions=tool_desc,
        current_datetime=_get_current_datetime(),
    )
    # Inject context block after the rendered prompt
    if context_block:
        system = system + context_block
    user_msg = state["messages"][-1].content if state["messages"] else ""

    try:
        action: AgentAction = await _run_llm_async(
            llm,
            "structured_completion",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            response_model=AgentAction,
            temperature=0.2,
        )
    except Exception as exc:
        # Content filter errors should not be retried with fallback
        if _is_content_filter_error(exc):
            logger.error("Content policy violation: %s", exc)
            return {"messages": [AIMessage(content=_content_filter_error_message(exc))]}

        logger.warning("Structured completion failed, falling back to text: %s", exc)
        try:
            text = await _run_llm_async(
                llm,
                "completion",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.2,
            )
            return {"messages": [AIMessage(content=str(text))]}
        except Exception as fallback_exc:
            # Check if fallback also hit content filter
            if _is_content_filter_error(fallback_exc):
                logger.error("Content policy violation in fallback: %s", fallback_exc)
                return {"messages": [AIMessage(content=_content_filter_error_message(fallback_exc))]}
            raise

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

    from noeagent.schemas import SubagentAction

    sa = SubagentAction(**sa_data)
    try:
        if sa.action == "spawn":
            from noeagent.config import NoeMode

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
            # Invoke a built-in specialized agent via SubagentManager
            subagent_manager = getattr(agent, "_subagent_manager", None)
            if subagent_manager is None:
                result = "SubagentManager not configured."
            else:
                # Check if this subagent requires explicit command
                from noeagent.commands import get_subagent_display_name

                subagent_name = sa.name
                requires_explicit = False

                # Check config for requires_explicit_command flag
                for cfg in agent.config.builtin:
                    cfg_name = getattr(cfg, "name", None) if hasattr(cfg, "name") else cfg.get("name")
                    if cfg_name == subagent_name:
                        requires_explicit = (
                            getattr(cfg, "requires_explicit_command", False)
                            if hasattr(cfg, "requires_explicit_command")
                            else cfg.get("requires_explicit_command", False)
                        )
                        break

                if requires_explicit:
                    display_name = get_subagent_display_name(subagent_name)
                    result = (
                        f"{display_name} cannot be auto-invoked. "
                        f"It requires explicit user selection (e.g. subagent selector or API subagent_names). "
                        f"For this task, use web_search tool instead to search for information. "
                        f"Do NOT try to invoke {display_name} again."
                    )
                else:
                    try:
                        result = await agent.invoke_subagent(subagent_name, sa.message)
                    except Exception as exc:
                        result = f"Failed to invoke built-in agent '{subagent_name}': {exc}"
        elif sa.action == "invoke_cli":
            # Invoke CLI subagent via SubagentManager (oneshot mode)
            subagent_manager = getattr(agent, "_subagent_manager", None)
            if subagent_manager is None or subagent_manager.get_provider(sa.name) is None:
                # Fallback: direct CLI adapter if SubagentManager has no entry
                cli_adapter = getattr(agent, "_cli_adapter", None)
                if cli_adapter is None:
                    result = "CLI subagent adapter not configured."
                else:
                    try:
                        cli_kwargs: dict[str, Any] = {}
                        if sa.allowed_tools is not None:
                            cli_kwargs["allowed_tools"] = sa.allowed_tools
                        if sa.skip_permissions is not None:
                            cli_kwargs["skip_permissions"] = sa.skip_permissions
                        exec_result = await cli_adapter.execute_oneshot(sa.name, sa.message, **cli_kwargs)
                        if hasattr(exec_result, "success"):
                            result = exec_result.content if exec_result.success else f"Error: {exec_result.error}"
                        else:
                            result = str(exec_result)
                    except Exception as exc:
                        result = f"Failed to invoke CLI agent '{sa.name}': {exc}"
            else:
                try:
                    result = await agent.invoke_subagent(sa.name, sa.message)
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
    completed = "\n".join(
        f"- {r.get('tool', 'unknown')}: {str(r.get('result', ''))[:200]}" for r in state.get("tool_results", [])
    )
    pm = get_prompt_manager()
    prompt = pm.render(
        "reflection",
        goal=goal,
        plan_steps=plan_steps or "No plan.",
        completed_results=completed or "None.",
    )
    reflection = await _run_llm_async(
        llm,
        "completion",
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
    completed = [str(r.get("result", ""))[:200] for r in state.get("tool_results", [])]
    new_plan = await planner.revise_plan(plan, state.get("reflection", ""), completed)
    await _persist_plan_to_memory(new_plan, memory_manager)
    return {"plan": new_plan}


def _is_no_task_finalize(goal: str, results: str) -> bool:
    """True when goal/results indicate no real task — skip full synthesis and return a short message."""
    goal_blank = not (goal and goal.strip())
    results_blank = not (results and results.strip())
    # Results often contain agent's own "no question" reply when user input was empty
    no_task_phrases = (
        "no specific question",
        "no specific task",
        "no specific research",
        "don't see a specific question",
        "lacks the necessary directives",
        "absence of a defined goal",
    )
    results_lower = (results or "").lower()
    results_say_no_task = any(p in results_lower for p in no_task_phrases)
    return goal_blank or results_blank or results_say_no_task


async def finalize_node(
    state: AgentState,
    *,
    llm: Any,
) -> dict[str, Any]:
    plan: TaskPlan | None = state.get("plan")
    goal = plan.goal if plan else ""
    results = "\n".join(
        f"- {r.get('tool', 'unknown')}: {str(r.get('result', ''))[:300]}" for r in state.get("tool_results", [])
    )
    if not results:
        last_msg = state["messages"][-1].content if state["messages"] else ""
        results = last_msg

    # Skip full synthesis for empty/error prompts to avoid redundant long output
    if _is_no_task_finalize(goal, results):
        if goal and goal.strip():
            answer = "No results to synthesize. Please provide a specific question or task."
        else:
            answer = "No question or task was provided. Please enter a specific request (e.g. a topic to research, a file to analyze, or code to run)."
        return {"final_answer": answer}

    pm = get_prompt_manager()
    prompt = pm.render(
        "finalize",
        goal=goal,
        results=results,
        current_datetime=_get_current_datetime(),
    )
    answer = await _run_llm_async(
        llm,
        "completion",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return {"final_answer": answer}
