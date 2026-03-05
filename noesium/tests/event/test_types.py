"""Tests for DomainEvent base class and all standard event types."""

import pytest

from noesium.core.event.envelope import AgentRef, TraceContext
from noesium.core.event.types import (
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


@pytest.fixture()
def producer():
    return AgentRef(agent_id="a1", agent_type="test")


@pytest.fixture()
def trace():
    return TraceContext()


EVENT_CASES = [
    (AgentStarted, {"agent_id": "a1", "agent_type": "test"}, "agent.started"),
    (AgentStopped, {"agent_id": "a1"}, "agent.stopped"),
    (NodeEntered, {"node_id": "n1", "graph_id": "g1"}, "kernel.node.entered"),
    (NodeCompleted, {"node_id": "n1", "graph_id": "g1", "duration_ms": 123.4}, "kernel.node.completed"),
    (CheckpointCreated, {"checkpoint_id": "cp1", "node_id": "n1"}, "kernel.checkpoint.created"),
    (CapabilityRegistered, {"capability_id": "c1", "version": "1.0", "agent_id": "a1"}, "capability.registered"),
    (
        CapabilityInvoked,
        {"caller_agent_id": "a1", "target_agent_id": "a2", "capability_id": "c1"},
        "capability.invoked",
    ),
    (CapabilityCompleted, {"capability_id": "c1", "caller_agent_id": "a1"}, "capability.completed"),
    (MemoryWritten, {"key": "k", "value_type": "str"}, "memory.written"),
    (TaskRequested, {"task_id": "t1", "capability_id": "c1"}, "task.requested"),
    (TaskCompleted, {"task_id": "t1"}, "task.completed"),
    (ErrorOccurred, {"error_type": "ValueError", "message": "boom"}, "system.error.occurred"),
]


@pytest.mark.parametrize("cls,kwargs,expected_type", EVENT_CASES, ids=[c[0].__name__ for c in EVENT_CASES])
class TestDomainEvents:
    def test_event_type(self, cls, kwargs, expected_type):
        event = cls(**kwargs)
        assert event.event_type() == expected_type

    def test_payload_contains_fields(self, cls, kwargs, expected_type):
        event = cls(**kwargs)
        payload = event.payload()
        for key, value in kwargs.items():
            assert payload[key] == value

    def test_to_envelope_roundtrip(self, cls, kwargs, expected_type, producer, trace):
        event = cls(**kwargs)
        envelope = event.to_envelope(producer=producer, trace=trace, correlation_id="corr-1")
        assert envelope.event_type == expected_type
        assert envelope.correlation_id == "corr-1"
        assert envelope.producer.agent_id == "a1"
        for key, value in kwargs.items():
            assert envelope.payload[key] == value


class TestDomainEventAbstract:
    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            DomainEvent()
