"""Tests for event envelope, AgentRef, TraceContext, and SignatureBlock."""

import pytest

from noesium.core.event.envelope import (
    AgentRef,
    EventEnvelope,
    SignatureBlock,
    TraceContext,
)


class TestAgentRef:
    def test_creation(self):
        ref = AgentRef(agent_id="a1", agent_type="search")
        assert ref.agent_id == "a1"
        assert ref.agent_type == "search"
        assert ref.runtime_id == "local"
        assert ref.instance_id  # auto-generated

    def test_custom_fields(self):
        ref = AgentRef(agent_id="a1", agent_type="search", runtime_id="cloud", instance_id="custom-id")
        assert ref.runtime_id == "cloud"
        assert ref.instance_id == "custom-id"


class TestTraceContext:
    def test_defaults(self):
        ctx = TraceContext()
        assert ctx.trace_id
        assert ctx.span_id
        assert ctx.parent_span_id is None
        assert ctx.depth == 0

    def test_child(self):
        parent = TraceContext()
        child = parent.child()
        assert child.trace_id == parent.trace_id
        assert child.parent_span_id == parent.span_id
        assert child.depth == parent.depth + 1
        assert child.span_id != parent.span_id

    def test_child_chain(self):
        root = TraceContext()
        c1 = root.child()
        c2 = c1.child()
        assert c2.depth == 2
        assert c2.trace_id == root.trace_id
        assert c2.parent_span_id == c1.span_id


class TestSignatureBlock:
    def test_creation(self):
        sig = SignatureBlock(algorithm="ed25519", public_key_id="key-1", signature="abc123")
        assert sig.algorithm == "ed25519"


class TestEventEnvelope:
    @pytest.fixture()
    def producer(self):
        return AgentRef(agent_id="agent-1", agent_type="search")

    @pytest.fixture()
    def trace(self):
        return TraceContext()

    def test_required_fields(self, producer, trace):
        env = EventEnvelope(
            event_type="test.event",
            producer=producer,
            trace=trace,
            payload={"key": "value"},
        )
        assert env.spec_version == "1.0.0"
        assert env.event_id
        assert env.event_type == "test.event"
        assert env.timestamp is not None
        assert env.payload == {"key": "value"}
        assert env.metadata == {}
        assert env.signature is None

    def test_optional_fields(self, producer, trace):
        env = EventEnvelope(
            event_type="test.event",
            producer=producer,
            trace=trace,
            payload={},
            causation_id="cause-1",
            correlation_id="corr-1",
            idempotency_key="idem-1",
            partition_key="part-1",
            ttl_ms=5000,
        )
        assert env.causation_id == "cause-1"
        assert env.correlation_id == "corr-1"
        assert env.ttl_ms == 5000

    def test_serialization_roundtrip(self, producer, trace):
        env = EventEnvelope(
            event_type="test.event",
            producer=producer,
            trace=trace,
            payload={"data": [1, 2, 3]},
        )
        json_str = env.model_dump_json()
        restored = EventEnvelope.model_validate_json(json_str)
        assert restored.event_id == env.event_id
        assert restored.payload == env.payload
        assert restored.producer.agent_id == env.producer.agent_id

    def test_unique_event_ids(self, producer, trace):
        e1 = EventEnvelope(event_type="t", producer=producer, trace=trace, payload={})
        e2 = EventEnvelope(event_type="t", producer=producer, trace=trace, payload={})
        assert e1.event_id != e2.event_id
