"""Event system: envelope, domain events, stores, and progress events (RFC-0002, RFC-1001, RFC-1007)."""

from .codec import canonicalize, deserialize, serialize
from .envelope import AgentRef, EventEnvelope, SignatureBlock, TraceContext
from .progress import ProgressCallback, ProgressEvent, ProgressEventType
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
    "ProgressCallback",
    "ProgressEvent",
    "ProgressEventType",
    "SignatureBlock",
    "TaskCompleted",
    "TaskRequested",
    "TraceContext",
    "canonicalize",
    "deserialize",
    "serialize",
]
