"""Structured output schemas for NoeAgent tool-calling (impl guide §3.3)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCallAction(BaseModel):
    """A single tool invocation request produced by the LLM."""

    tool_name: str = Field(description="Registered tool name to invoke")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Keyword arguments to pass to the tool",
    )


class SubagentAction(BaseModel):
    """Request to spawn or interact with a child NoeAgent."""

    action: Literal["spawn", "interact"] = Field(
        description="Whether to create a new subagent or send a message to an existing one",
    )
    name: str = Field(description="Subagent name (used as identifier)")
    message: str = Field(default="", description="Message/task to send to the subagent")
    mode: str = Field(default="agent", description="Subagent mode: 'ask' or 'agent'")


class AgentAction(BaseModel):
    """Structured decision produced by execute_step_node via structured_completion.

    Exactly one of ``tool_calls``, ``subagent``, or ``text_response`` should be
    populated per invocation.
    """

    thought: str = Field(
        description="Brief reasoning about what to do next",
    )
    tool_calls: list[ToolCallAction] | None = Field(
        default=None,
        description="Tool invocations to perform. Set when a tool is needed.",
    )
    subagent: SubagentAction | None = Field(
        default=None,
        description="Subagent spawn/interact request. Set when delegation is needed.",
    )
    text_response: str | None = Field(
        default=None,
        description="Direct text answer when no tool or subagent is needed.",
    )
    mark_step_complete: bool = Field(
        default=False,
        description="Whether the current plan step is finished after this action.",
    )
