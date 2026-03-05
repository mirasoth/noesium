"""Tests for CognitiveProjection."""

import pytest

from noesium.core.event.envelope import AgentRef, EventEnvelope, TraceContext
from noesium.core.projection.cognitive import CognitiveProjection


def _env(event_type: str, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        producer=AgentRef(agent_id="a", agent_type="test"),
        trace=TraceContext(),
        payload=payload,
    )


class TestCognitiveProjection:
    @pytest.fixture()
    def proj(self):
        return CognitiveProjection()

    def test_initial_state(self, proj):
        state = proj.initial_state()
        assert state["memory_entries"] == {}
        assert state["write_count"] == 0

    def test_memory_written(self, proj):
        events = [
            _env("memory.written", {"key": "name", "value": "Alice", "value_type": "str"}),
        ]
        state = proj.fold(events)
        assert state["write_count"] == 1
        assert state["memory_entries"]["name"]["value"] == "Alice"
        assert state["memory_entries"]["name"]["value_type"] == "str"

    def test_multiple_writes_same_key_last_wins(self, proj):
        events = [
            _env("memory.written", {"key": "x", "value": 1, "value_type": "int"}),
            _env("memory.written", {"key": "x", "value": 2, "value_type": "int"}),
        ]
        state = proj.fold(events)
        assert state["memory_entries"]["x"]["value"] == 2
        assert state["write_count"] == 2

    def test_error_recorded_in_reasoning_traces(self, proj):
        events = [
            _env("system.error.occurred", {"error_type": "ValueError", "message": "bad input"}),
        ]
        state = proj.fold(events)
        assert len(state["reasoning_traces"]) == 1
        assert state["reasoning_traces"][0]["error_type"] == "ValueError"

    def test_ignores_unrelated_events(self, proj):
        events = [_env("kernel.node.entered", {"node_id": "n1", "graph_id": "g1"})]
        state = proj.fold(events)
        assert state["write_count"] == 0
