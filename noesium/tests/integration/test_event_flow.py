"""Integration test: event store -> projection -> state derivation."""

import pytest

from noesium.core.event.envelope import AgentRef, EventEnvelope, TraceContext
from noesium.core.event.store import InMemoryEventStore
from noesium.core.event.types import MemoryWritten, NodeCompleted, NodeEntered
from noesium.core.projection.base import ProjectionEngine
from noesium.core.projection.cognitive import CognitiveProjection
from noesium.core.projection.execution import ExecutionProjection

PRODUCER = AgentRef(agent_id="integration-agent", agent_type="test")
TRACE = TraceContext()


def _emit(event) -> EventEnvelope:
    return event.to_envelope(producer=PRODUCER, trace=TRACE)


@pytest.mark.integration
class TestEventFlow:
    @pytest.mark.asyncio
    async def test_events_to_execution_projection(self):
        store = InMemoryEventStore()
        engine = ProjectionEngine(event_store=store)
        engine.register("exec", ExecutionProjection())

        events = [
            NodeEntered(node_id="parse", graph_id="g1"),
            NodeCompleted(node_id="parse", graph_id="g1", duration_ms=20.0),
            NodeEntered(node_id="transform", graph_id="g1"),
            NodeCompleted(node_id="transform", graph_id="g1", duration_ms=50.0),
        ]
        for ev in events:
            await store.append(_emit(ev))

        state = await engine.get_state("exec")
        assert state["total_nodes_entered"] == 2
        assert state["total_nodes_completed"] == 2
        assert state["node_executions"]["parse"]["completed"] == 1
        assert state["node_executions"]["transform"]["total_ms"] == 50.0

    @pytest.mark.asyncio
    async def test_events_to_cognitive_projection(self):
        store = InMemoryEventStore()
        engine = ProjectionEngine(event_store=store)
        engine.register("cog", CognitiveProjection())

        events = [
            MemoryWritten(key="user_name", value="Alice", value_type="str"),
            MemoryWritten(key="preference", value="dark_mode", value_type="str"),
        ]
        for ev in events:
            await store.append(_emit(ev))

        state = await engine.get_state("cog")
        assert state["write_count"] == 2
        assert state["memory_entries"]["user_name"]["value"] == "Alice"

    @pytest.mark.asyncio
    async def test_rebuild_matches_incremental(self):
        store = InMemoryEventStore()
        engine = ProjectionEngine(event_store=store)
        engine.register("exec", ExecutionProjection())

        for i in range(5):
            await store.append(_emit(NodeEntered(node_id=f"n{i}", graph_id="g")))

        incremental = await engine.get_state("exec")
        rebuilt = await engine.rebuild("exec")
        assert incremental["total_nodes_entered"] == rebuilt["total_nodes_entered"]
