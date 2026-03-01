"""Event system: envelope, domain events, and stores (RFC-0002, RFC-1001)."""

from .codec import canonicalize, deserialize, serialize
from .envelope import AgentRef, EventEnvelope, SignatureBlock, TraceContext
from .store import EventStore, FileEventStore, InMemoryEventStore
from .types import (
    AgentStarted,
    AgentStopped,
    CapabilityCompleted,
    CapabilityInvoked,
    CapabilityRegistered,
    CheckpointCreated,
    DomainEvent,
    ErrorOccurred,
    MemoryWritten,
    NodeCompleted,
    NodeEntered,
    TaskCompleted,
    TaskRequested,
)

__all__ = [
    "AgentRef",
    "AgentStarted",
    "AgentStopped",
    "CapabilityCompleted",
    "CapabilityInvoked",
    "CapabilityRegistered",
    "CheckpointCreated",
    "DomainEvent",
    "ErrorOccurred",
    "EventEnvelope",
    "EventStore",
    "FileEventStore",
    "InMemoryEventStore",
    "MemoryWritten",
    "NodeCompleted",
    "NodeEntered",
    "SignatureBlock",
    "TaskCompleted",
    "TaskRequested",
    "TraceContext",
    "canonicalize",
    "deserialize",
    "serialize",
]
