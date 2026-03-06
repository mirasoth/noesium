"""Tests for BaseProjection and ProjectionEngine."""

import pytest

from noesium.core.event.envelope import AgentRef, EventEnvelope, TraceContext
from noesium.core.event.store import InMemoryEventStore
from noesium.core.projection.base import BaseProjection, ProjectionEngine


def _make_envelope(event_type: str, payload: dict | None = None) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        producer=AgentRef(agent_id="a", agent_type="test"),
        trace=TraceContext(),
        payload=payload or {},
    )


class CounterProjection(BaseProjection[int]):
    """Simple projection that counts events."""

    def initial_state(self) -> int:
        return 0

    def apply(self, state: int, event: EventEnvelope) -> int:
        return state + 1


class TestBaseProjection:
    def test_fold_empty(self):
        p = CounterProjection()
        assert p.fold([]) == 0

    def test_fold_multiple(self):
        p = CounterProjection()
        events = [_make_envelope("x") for _ in range(5)]
        assert p.fold(events) == 5


class TestProjectionEngine:
    @pytest.fixture()
    def store(self):
        return InMemoryEventStore()

    @pytest.fixture()
    def engine(self, store):
        return ProjectionEngine(event_store=store)

    @pytest.mark.asyncio
    async def test_register_and_get_state_empty(self, engine):
        engine.register("counter", CounterProjection())
        state = await engine.get_state("counter")
        assert state == 0

    @pytest.mark.asyncio
    async def test_get_state_incremental(self, store, engine):
        engine.register("counter", CounterProjection())
        await store.append(_make_envelope("a"))
        await store.append(_make_envelope("b"))

        state = await engine.get_state("counter")
        assert state == 2

        await store.append(_make_envelope("c"))
        state = await engine.get_state("counter")
        assert state == 3

    @pytest.mark.asyncio
    async def test_rebuild(self, store, engine):
        engine.register("counter", CounterProjection())
        for _ in range(4):
            await store.append(_make_envelope("x"))

        state = await engine.rebuild("counter")
        assert state == 4

    @pytest.mark.asyncio
    async def test_apply_event(self, engine):
        engine.register("counter", CounterProjection())
        env = _make_envelope("x")
        await engine.apply_event(env)
        state = await engine.get_state("counter")
        assert state == 1

    @pytest.mark.asyncio
    async def test_multiple_projections(self, store, engine):
        engine.register("c1", CounterProjection())
        engine.register("c2", CounterProjection())
        await store.append(_make_envelope("x"))

        s1 = await engine.get_state("c1")
        s2 = await engine.get_state("c2")
        assert s1 == 1
        assert s2 == 1
