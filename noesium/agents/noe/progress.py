"""Typed progress event protocol for NoeAgent (impl guide §5.5).

Provides a unified event model consumed by both the Rich TUI (compact display)
and library-mode integrations (structured output).  Each event carries a short
``summary`` suitable for terminal rendering and a verbose ``detail`` for
session-level offline logging.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ProgressEventType(str, Enum):
    """Enumeration of all progress event kinds."""

    SESSION_START = "session.start"
    SESSION_END = "session.end"
    PLAN_CREATED = "plan.created"
    PLAN_REVISED = "plan.revised"
    STEP_START = "step.start"
    STEP_COMPLETE = "step.complete"
    TOOL_START = "tool.start"
    TOOL_END = "tool.end"
    SUBAGENT_START = "subagent.start"
    SUBAGENT_PROGRESS = "subagent.progress"
    SUBAGENT_END = "subagent.end"
    THINKING = "thinking"
    TEXT_CHUNK = "text.chunk"
    PARTIAL_RESULT = "partial.result"
    REFLECTION = "reflection"
    FINAL_ANSWER = "final.answer"
    ERROR = "error"


class ProgressEvent(BaseModel):
    """Single flat event emitted during agent execution.

    The ``summary`` field always contains a short one-liner suitable for TUI
    rendering.  The ``detail`` field holds verbose content (full tool args /
    results, reflection text, etc.) intended for session logging only.
    """

    type: ProgressEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str = ""
    sequence: int = 0

    node: str | None = None
    step_index: int | None = None
    step_desc: str | None = None

    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: str | None = None

    subagent_id: str | None = None
    text: str | None = None
    summary: str | None = None
    detail: str | None = None

    plan_snapshot: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class ProgressCallback(Protocol):
    """Push-style callback for library consumers."""

    async def on_progress(self, event: ProgressEvent) -> None: ...
