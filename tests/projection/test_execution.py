"""Tests for ExecutionProjection."""

import pytest

from noesium.core.event.envelope import AgentRef, EventEnvelope, TraceContext
from noesium.core.projection.execution import ExecutionProjection


def _env(event_type: str, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        producer=AgentRef(agent_id="a", agent_type="test"),
        trace=TraceContext(),
        payload=payload,
    )


class TestExecutionProjection:
    @pytest.fixture()
    def proj(self):
        return ExecutionProjection()

    def test_initial_state(self, proj):
        state = proj.initial_state()
        assert state["total_nodes_entered"] == 0
        assert state["total_nodes_completed"] == 0

    def test_node_entered(self, proj):
        state = proj.fold([_env("kernel.node.entered", {"node_id": "n1", "graph_id": "g1"})])
        assert state["total_nodes_entered"] == 1
        assert state["node_executions"]["n1"]["entered"] == 1

    def test_node_completed(self, proj):
        events = [
            _env("kernel.node.entered", {"node_id": "n1", "graph_id": "g1"}),
            _env("kernel.node.completed", {"node_id": "n1", "graph_id": "g1", "duration_ms": 50.0}),
        ]
        state = proj.fold(events)
        assert state["total_nodes_completed"] == 1
        assert state["node_executions"]["n1"]["completed"] == 1
        assert state["node_executions"]["n1"]["total_ms"] == 50.0

    def test_task_lifecycle(self, proj):
        events = [
            _env("task.requested", {"task_id": "t1", "capability_id": "c1"}),
            _env("task.completed", {"task_id": "t1"}),
        ]
        state = proj.fold(events)
        assert state["task_states"]["t1"] == "completed"

    def test_task_failed(self, proj):
        events = [
            _env("task.requested", {"task_id": "t2", "capability_id": "c1"}),
            _env("task.completed", {"task_id": "t2", "error": "timeout"}),
        ]
        state = proj.fold(events)
        assert state["task_states"]["t2"] == "failed"

    def test_ignores_unrelated_events(self, proj):
        events = [_env("memory.written", {"key": "k", "value": "v"})]
        state = proj.fold(events)
        assert state["total_nodes_entered"] == 0
