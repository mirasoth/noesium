"""Conditional routing logic for NoeAgent state graph."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noeagent.config import NoeConfig
    from noeagent.state import AgentState


def route_after_execute(state: "AgentState", config: "NoeConfig") -> str:
    """Route after execute_step node.

    Args:
        state: Current agent state
        config: Agent configuration

    Returns:
        Next node name
    """
    plan = state.get("plan")
    if plan and plan.is_complete:
        return "finalize"

    last_msg = state["messages"][-1] if state.get("messages") else None
    if last_msg and getattr(last_msg, "tool_calls", None):
        return "tool_node"
    if last_msg and getattr(last_msg, "additional_kwargs", {}).get("subagent_action"):
        return "subagent_node"

    iteration = state.get("iteration", 0)
    if iteration >= config.max_iterations:
        return "finalize"
    if iteration > 0 and iteration % config.reflection_interval == 0:
        return "reflect"
    return "execute_step"


def route_after_reflect(state: "AgentState") -> str:
    """Route after reflect node.

    Args:
        state: Current agent state

    Returns:
        Next node name
    """
    reflection = state.get("reflection", "")
    if "REVISE" in reflection.upper():
        return "revise_plan"
    plan = state.get("plan")
    return "finalize" if plan and plan.is_complete else "execute_step"
