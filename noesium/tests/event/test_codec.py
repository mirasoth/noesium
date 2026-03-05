"""Tests for event serialization and canonicalization."""

import json

import pytest

from noesium.core.event.codec import canonicalize, deserialize, serialize
from noesium.core.event.envelope import AgentRef, EventEnvelope, TraceContext


@pytest.fixture()
def envelope():
    return EventEnvelope(
        event_type="test.event",
        producer=AgentRef(agent_id="a1", agent_type="test"),
        trace=TraceContext(trace_id="t1", span_id="s1"),
        payload={"z_key": 1, "a_key": 2},
    )


class TestCanonicalize:
    def test_sorted_keys(self, envelope):
        canon = canonicalize(envelope)
        data = json.loads(canon)
        keys = list(data.keys())
        assert keys == sorted(keys)

    def test_no_extra_whitespace(self, envelope):
        canon = canonicalize(envelope)
        assert "  " not in canon
        assert ": " not in canon

    def test_deterministic(self, envelope):
        assert canonicalize(envelope) == canonicalize(envelope)

    def test_payload_keys_sorted(self, envelope):
        canon = canonicalize(envelope)
        assert canon.index('"a_key"') < canon.index('"z_key"')


class TestSerializeDeserialize:
    def test_roundtrip(self, envelope):
        raw = serialize(envelope)
        restored = deserialize(raw)
        assert restored.event_id == envelope.event_id
        assert restored.event_type == envelope.event_type
        assert restored.payload == envelope.payload

    def test_serialize_is_valid_json(self, envelope):
        raw = serialize(envelope)
        parsed = json.loads(raw)
        assert parsed["event_type"] == "test.event"
