"""Subagent invocation request and result models (RFC-1006 Sections 5.2 and 5.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


@dataclass
class SubagentInvocationRequest:
    """Request to invoke a subagent.

    Encapsulates all information needed to invoke a subagent, including
    the task message, execution context, and policy overrides.

    Attributes:
        subagent_id: ID of the subagent to invoke.
        message: The task message/prompt for the subagent.
        request_id: Unique identifier for this request.
        context: Additional context data for the invocation.
        execution_mode: Whether this is a oneshot or session-based invocation.
        timeout_s: Optional timeout in seconds.
        cancellation_token: Optional token for cancellation support.
        policy_overrides: Optional policy overrides for this invocation.
        metadata: Optional metadata for tracking/observability.
    """

    subagent_id: str
    message: str
    request_id: str = field(default_factory=lambda: str(uuid4()))
    context: dict[str, Any] = field(default_factory=dict)
    execution_mode: Literal["oneshot", "session"] = "oneshot"
    timeout_s: float | None = None
    cancellation_token: str | None = None
    policy_overrides: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_timeout(self, timeout_s: float) -> SubagentInvocationRequest:
        """Return a copy with the specified timeout."""
        return SubagentInvocationRequest(
            subagent_id=self.subagent_id,
            message=self.message,
            request_id=self.request_id,
            context=self.context.copy(),
            execution_mode=self.execution_mode,
            timeout_s=timeout_s,
            cancellation_token=self.cancellation_token,
            policy_overrides=self.policy_overrides.copy(),
            metadata=self.metadata.copy(),
        )

    def with_context(self, **extra_context: Any) -> SubagentInvocationRequest:
        """Return a copy with additional context."""
        new_context = {**self.context, **extra_context}
        return SubagentInvocationRequest(
            subagent_id=self.subagent_id,
            message=self.message,
            request_id=self.request_id,
            context=new_context,
            execution_mode=self.execution_mode,
            timeout_s=self.timeout_s,
            cancellation_token=self.cancellation_token,
            policy_overrides=self.policy_overrides.copy(),
            metadata=self.metadata.copy(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "subagent_id": self.subagent_id,
            "message": self.message,
            "context": self.context,
            "execution_mode": self.execution_mode,
            "timeout_s": self.timeout_s,
            "cancellation_token": self.cancellation_token,
            "policy_overrides": self.policy_overrides,
            "metadata": self.metadata,
        }


@dataclass
class SubagentInvocationResult:
    """Result from a subagent invocation.

    Encapsulates the outcome of a subagent invocation, including the
    final output, any artifacts produced, and error information.

    Attributes:
        request_id: ID of the original request.
        subagent_id: ID of the subagent that executed.
        success: Whether the invocation succeeded.
        final_text: The final text output from the subagent.
        structured_output: Optional structured output data.
        artifacts: List of artifacts produced (files, images, etc.).
        usage: Resource usage information (tokens, time, cost).
        error_code: Error code if success is False.
        error_message: Human-readable error message if success is False.
        metadata: Additional metadata about the execution.
        timestamp: When the result was created.
    """

    request_id: str
    subagent_id: str
    success: bool
    final_text: str = ""
    structured_output: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def success_result(
        cls,
        request_id: str,
        subagent_id: str,
        final_text: str,
        structured_output: dict[str, Any] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        usage: dict[str, Any] | None = None,
        **metadata: Any,
    ) -> SubagentInvocationResult:
        """Create a successful result."""
        return cls(
            request_id=request_id,
            subagent_id=subagent_id,
            success=True,
            final_text=final_text,
            structured_output=structured_output,
            artifacts=artifacts or [],
            usage=usage,
            metadata=metadata,
        )

    @classmethod
    def failure_result(
        cls,
        request_id: str,
        subagent_id: str,
        error_code: str,
        error_message: str,
        partial_text: str = "",
        **metadata: Any,
    ) -> SubagentInvocationResult:
        """Create a failure result."""
        return cls(
            request_id=request_id,
            subagent_id=subagent_id,
            success=False,
            final_text=partial_text,
            error_code=error_code,
            error_message=error_message,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "request_id": self.request_id,
            "subagent_id": self.subagent_id,
            "success": self.success,
            "final_text": self.final_text,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

        if self.structured_output is not None:
            result["structured_output"] = self.structured_output
        if self.artifacts:
            result["artifacts"] = self.artifacts
        if self.usage is not None:
            result["usage"] = self.usage
        if self.error_code is not None:
            result["error_code"] = self.error_code
        if self.error_message is not None:
            result["error_message"] = self.error_message

        return result
