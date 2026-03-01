"""Tool domain events (RFC-2004 §6)."""

from __future__ import annotations

from typing import Any

from noesium.core.event.types import DomainEvent


class ToolInvoked(DomainEvent):
    tool_id: str
    tool_name: str
    input_data: dict[str, Any]
    source: str

    def event_type(self) -> str:
        return "tool.invoked"


class ToolCompleted(DomainEvent):
    tool_id: str
    tool_name: str
    output_data: Any
    duration_ms: int

    def event_type(self) -> str:
        return "tool.completed"


class ToolFailed(DomainEvent):
    tool_id: str
    tool_name: str
    error: str
    duration_ms: int

    def event_type(self) -> str:
        return "tool.failed"


class ToolTimeout(DomainEvent):
    tool_id: str
    tool_name: str
    timeout_ms: int

    def event_type(self) -> str:
        return "tool.timeout"


class ToolRegistered(DomainEvent):
    tool_id: str
    tool_name: str
    source: str
    capabilities: dict[str, Any]

    def event_type(self) -> str:
        return "tool.registered"
