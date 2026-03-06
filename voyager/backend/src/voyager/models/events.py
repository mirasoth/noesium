"""WebSocket event models for Voyager."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WebSocketEvent(BaseModel):
    """Base WebSocket event structure."""

    type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    data: dict[str, Any] = Field(default_factory=dict)


class ProgressEventData(BaseModel):
    """Progress event payload mapped from NoeAgent ProgressEvent."""

    event_type: str  # step.start, step.complete, tool.start, etc.
    session_id: str = ""
    sequence: int = 0
    summary: str | None = None
    detail: str | None = None
    step_index: int | None = None
    step_desc: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: str | None = None
    text: str | None = None
    error: str | None = None
