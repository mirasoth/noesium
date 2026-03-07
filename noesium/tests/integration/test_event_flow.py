"""Integration test: event store -> projection -> state derivation."""

import pytest

from noesium.core.event.envelope import AgentRef, EventEnvelope, TraceContext
from noesium.core.event.store import InMemoryEventStore
from noesium.core.event.types import MemoryWritten
from noesium.core.projection.base import ProjectionEngine
from noesium.core.projection.cognitive import CognitiveProjection

PRODUCER = AgentRef(agent_id="integration-agent", agent_type="test")
TRACE = TraceContext()


def _emit(event) -> EventEnvelope:
    return event.to_envelope(producer=PRODUCER, trace=TRACE)


@pytest.mark.integration
class TestEventFlow:
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
        engine.register("cog", CognitiveProjection())

        for i in range(5):
            await store.append(_emit(MemoryWritten(key=f"key{i}", value=f"val{i}", value_type="str")))

        incremental = await engine.get_state("cog")
        rebuilt = await engine.rebuild("cog")
        assert incremental["write_count"] == rebuilt["write_count"]
