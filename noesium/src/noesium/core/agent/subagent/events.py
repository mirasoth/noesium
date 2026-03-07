"""Subagent progress event types and envelope (RFC-1006 Section 5.4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class SubagentEventType(str, Enum):
    """Normalized event types for subagent progress streaming."""

    SUBAGENT_START = "subagent.start"
    SUBAGENT_PROGRESS = "subagent.progress"
    SUBAGENT_THOUGHT = "subagent.thought"
    SUBAGENT_TOOL_CALL = "subagent.tool_call"
    SUBAGENT_TOOL_RESULT = "subagent.tool_result"
    SUBAGENT_HITL_REQUEST = "subagent.hitl_request"
    SUBAGENT_HITL_RESPONSE = "subagent.hitl_response"
    SUBAGENT_WARNING = "subagent.warning"
    SUBAGENT_ERROR = "subagent.error"
    SUBAGENT_END = "subagent.end"


@dataclass
class SubagentProgressEvent:
    """Event emitted during subagent execution for progress streaming.

    Provides a normalized envelope for all subagent events, enabling
    consistent handling by parent orchestrators and UI components.

    Attributes:
        event_type: Type of the event.
        request_id: ID of the invocation request this event belongs to.
        subagent_id: ID of the subagent emitting this event.
        summary: Short human-readable summary of the event.
        detail: Optional detailed information.
        payload: Optional structured payload data.
        event_id: Unique identifier for this event.
        timestamp: When this event was created.
        sequence: Sequence number within the request (for ordering).

        HITL-specific fields:
        hitl_prompt: The prompt/question for the human operator.
        hitl_options: Optional predefined choices for HITL.
        hitl_timeout_s: Optional timeout before auto-cancel.
        hitl_input: Input received from human (for HITL_RESPONSE).

        Tool-specific fields:
        tool_name: Name of the tool being called/completed.
        tool_args: Arguments passed to the tool.
        tool_result: Result from tool execution.

        Error fields:
        error_code: Machine-readable error code.
        error_message: Human-readable error message.
    """

    event_type: SubagentEventType
    request_id: str
    subagent_id: str
    summary: str = ""
    detail: str | None = None
    payload: dict[str, Any] | None = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sequence: int = 0

    # HITL fields
    hitl_prompt: str | None = None
    hitl_options: list[str] | None = None
    hitl_timeout_s: float | None = None
    hitl_input: Any | None = None

    # Tool fields
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: Any | None = None

    # Error fields
    error_code: str | None = None
    error_message: str | None = None

    def is_terminal(self) -> bool:
        """Check if this is a terminal event (END or ERROR)."""
        return self.event_type in (SubagentEventType.SUBAGENT_END, SubagentEventType.SUBAGENT_ERROR)

    def is_hitl_request(self) -> bool:
        """Check if this event requires human input."""
        return self.event_type == SubagentEventType.SUBAGENT_HITL_REQUEST

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "event_type": self.event_type.value,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "request_id": self.request_id,
            "subagent_id": self.subagent_id,
            "summary": self.summary,
            "sequence": self.sequence,
        }

        if self.detail is not None:
            result["detail"] = self.detail
        if self.payload is not None:
            result["payload"] = self.payload
        if self.hitl_prompt is not None:
            result["hitl_prompt"] = self.hitl_prompt
        if self.hitl_options is not None:
            result["hitl_options"] = self.hitl_options
        if self.hitl_timeout_s is not None:
            result["hitl_timeout_s"] = self.hitl_timeout_s
        if self.hitl_input is not None:
            result["hitl_input"] = self.hitl_input
        if self.tool_name is not None:
            result["tool_name"] = self.tool_name
        if self.tool_args is not None:
            result["tool_args"] = self.tool_args
        if self.tool_result is not None:
            result["tool_result"] = self.tool_result
        if self.error_code is not None:
            result["error_code"] = self.error_code
        if self.error_message is not None:
            result["error_message"] = self.error_message

        return result

    @classmethod
    def start(
        cls,
        request_id: str,
        subagent_id: str,
        summary: str = "Subagent execution started",
        **kwargs: Any,
    ) -> SubagentProgressEvent:
        """Create a SUBAGENT_START event."""
        return cls(
            event_type=SubagentEventType.SUBAGENT_START,
            request_id=request_id,
            subagent_id=subagent_id,
            summary=summary,
            **kwargs,
        )

    @classmethod
    def progress(
        cls,
        request_id: str,
        subagent_id: str,
        summary: str,
        detail: str | None = None,
        **kwargs: Any,
    ) -> SubagentProgressEvent:
        """Create a SUBAGENT_PROGRESS event."""
        return cls(
            event_type=SubagentEventType.SUBAGENT_PROGRESS,
            request_id=request_id,
            subagent_id=subagent_id,
            summary=summary,
            detail=detail,
            **kwargs,
        )

    @classmethod
    def thought(
        cls,
        request_id: str,
        subagent_id: str,
        thought: str,
        **kwargs: Any,
    ) -> SubagentProgressEvent:
        """Create a SUBAGENT_THOUGHT event."""
        return cls(
            event_type=SubagentEventType.SUBAGENT_THOUGHT,
            request_id=request_id,
            subagent_id=subagent_id,
            summary="Intermediate reasoning",
            detail=thought,
            **kwargs,
        )

    @classmethod
    def tool_call(
        cls,
        request_id: str,
        subagent_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        **kwargs: Any,
    ) -> SubagentProgressEvent:
        """Create a SUBAGENT_TOOL_CALL event."""
        return cls(
            event_type=SubagentEventType.SUBAGENT_TOOL_CALL,
            request_id=request_id,
            subagent_id=subagent_id,
            summary=f"Calling tool: {tool_name}",
            tool_name=tool_name,
            tool_args=tool_args,
            **kwargs,
        )

    @classmethod
    def create_tool_result(
        cls,
        request_id: str,
        subagent_id: str,
        tool_name: str,
        result: Any,
        **kwargs: Any,
    ) -> SubagentProgressEvent:
        """Create a SUBAGENT_TOOL_RESULT event."""
        return cls(
            event_type=SubagentEventType.SUBAGENT_TOOL_RESULT,
            request_id=request_id,
            subagent_id=subagent_id,
            summary=f"Tool result: {tool_name}",
            tool_name=tool_name,
            tool_result=result,
            **kwargs,
        )

    @classmethod
    def hitl_request(
        cls,
        request_id: str,
        subagent_id: str,
        prompt: str,
        options: list[str] | None = None,
        timeout_s: float | None = None,
        **kwargs: Any,
    ) -> SubagentProgressEvent:
        """Create a SUBAGENT_HITL_REQUEST event."""
        return cls(
            event_type=SubagentEventType.SUBAGENT_HITL_REQUEST,
            request_id=request_id,
            subagent_id=subagent_id,
            summary="Awaiting human input",
            hitl_prompt=prompt,
            hitl_options=options,
            hitl_timeout_s=timeout_s,
            **kwargs,
        )

    @classmethod
    def hitl_response(
        cls,
        request_id: str,
        subagent_id: str,
        input_data: Any,
        **kwargs: Any,
    ) -> SubagentProgressEvent:
        """Create a SUBAGENT_HITL_RESPONSE event."""
        return cls(
            event_type=SubagentEventType.SUBAGENT_HITL_RESPONSE,
            request_id=request_id,
            subagent_id=subagent_id,
            summary="Human input received",
            hitl_input=input_data,
            **kwargs,
        )

    @classmethod
    def warning(
        cls,
        request_id: str,
        subagent_id: str,
        message: str,
        **kwargs: Any,
    ) -> SubagentProgressEvent:
        """Create a SUBAGENT_WARNING event."""
        return cls(
            event_type=SubagentEventType.SUBAGENT_WARNING,
            request_id=request_id,
            subagent_id=subagent_id,
            summary=message,
            **kwargs,
        )

    @classmethod
    def error(
        cls,
        request_id: str,
        subagent_id: str,
        error_code: str,
        error_message: str,
        **kwargs: Any,
    ) -> SubagentProgressEvent:
        """Create a SUBAGENT_ERROR event."""
        return cls(
            event_type=SubagentEventType.SUBAGENT_ERROR,
            request_id=request_id,
            subagent_id=subagent_id,
            summary=f"Error: {error_code}",
            error_code=error_code,
            error_message=error_message,
            **kwargs,
        )

    @classmethod
    def end(
        cls,
        request_id: str,
        subagent_id: str,
        summary: str = "Subagent execution completed",
        detail: str | None = None,
        **kwargs: Any,
    ) -> SubagentProgressEvent:
        """Create a SUBAGENT_END event."""
        return cls(
            event_type=SubagentEventType.SUBAGENT_END,
            request_id=request_id,
            subagent_id=subagent_id,
            summary=summary,
            detail=detail,
            **kwargs,
        )


# Standard error codes (RFC-1008 Section 8)
class SubagentErrorCode(str, Enum):
    """Standard error codes for subagent failures."""

    SUBAGENT_NOT_FOUND = "SUBAGENT_NOT_FOUND"
    SUBAGENT_UNHEALTHY = "SUBAGENT_UNHEALTHY"
    SUBAGENT_POLICY_DENIED = "SUBAGENT_POLICY_DENIED"
    SUBAGENT_TIMEOUT = "SUBAGENT_TIMEOUT"
    SUBAGENT_CANCELLED = "SUBAGENT_CANCELLED"
    SUBAGENT_BACKEND_ERROR = "SUBAGENT_BACKEND_ERROR"
    SUBAGENT_PROTOCOL_ERROR = "SUBAGENT_PROTOCOL_ERROR"
    SUBAGENT_HITL_TIMEOUT = "SUBAGENT_HITL_TIMEOUT"
