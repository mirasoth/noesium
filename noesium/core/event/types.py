"""Domain event base class and standard event types (RFC-1001 Section 6.2)."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from pydantic import BaseModel

from .envelope import AgentRef, EventEnvelope, TraceContext


class DomainEvent(BaseModel):
    """Typed domain event that produces an EventEnvelope."""

    @abstractmethod
    def event_type(self) -> str: ...

    def payload(self) -> dict[str, Any]:
        return self.model_dump()

    def to_envelope(
        self,
        producer: AgentRef,
        trace: TraceContext,
        causation_id: str | None = None,
        correlation_id: str | None = None,
    ) -> EventEnvelope:
        return EventEnvelope(
            event_type=self.event_type(),
            producer=producer,
            trace=trace,
            causation_id=causation_id,
            correlation_id=correlation_id,
            payload=self.payload(),
        )


# --- Agent lifecycle ---


class AgentStarted(DomainEvent):
    agent_id: str
    agent_type: str

    def event_type(self) -> str:
        return "agent.started"


class AgentStopped(DomainEvent):
    agent_id: str
    reason: str = ""

    def event_type(self) -> str:
        return "agent.stopped"


# --- Kernel node lifecycle ---


class NodeEntered(DomainEvent):
    node_id: str
    graph_id: str

    def event_type(self) -> str:
        return "kernel.node.entered"


class NodeCompleted(DomainEvent):
    node_id: str
    graph_id: str
    duration_ms: float

    def event_type(self) -> str:
        return "kernel.node.completed"


class CheckpointCreated(DomainEvent):
    checkpoint_id: str
    node_id: str

    def event_type(self) -> str:
        return "kernel.checkpoint.created"


# --- Capability lifecycle ---


class CapabilityRegistered(DomainEvent):
    capability_id: str
    version: str
    agent_id: str

    def event_type(self) -> str:
        return "capability.registered"


class CapabilityInvoked(DomainEvent):
    caller_agent_id: str
    target_agent_id: str
    capability_id: str

    def event_type(self) -> str:
        return "capability.invoked"


class CapabilityCompleted(DomainEvent):
    capability_id: str
    caller_agent_id: str
    result: Any = None
    error: str | None = None

    def event_type(self) -> str:
        return "capability.completed"


# --- Memory ---


class MemoryWritten(DomainEvent):
    key: str
    value_type: str
    value: Any = None

    def event_type(self) -> str:
        return "memory.written"


# --- Task delegation ---


class TaskRequested(DomainEvent):
    task_id: str
    capability_id: str
    task_payload: dict[str, Any] = {}

    def event_type(self) -> str:
        return "task.requested"


class TaskCompleted(DomainEvent):
    task_id: str
    result: Any = None
    error: str | None = None

    def event_type(self) -> str:
        return "task.completed"


# --- Errors ---


class ErrorOccurred(DomainEvent):
    error_type: str
    message: str
    original_event_id: str | None = None
    stack_trace: str | None = None

    def event_type(self) -> str:
        return "system.error.occurred"
