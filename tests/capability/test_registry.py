"""Tests for CapabilityRegistry."""

import pytest

from noesium.core.capability.models import Capability
from noesium.core.capability.registry import CapabilityRegistry
from noesium.core.event.store import InMemoryEventStore
from noesium.core.projection.base import ProjectionEngine


class TestCapabilityRegistry:
    @pytest.fixture()
    def store(self):
        return InMemoryEventStore()

    @pytest.fixture()
    def engine(self, store):
        return ProjectionEngine(event_store=store)

    @pytest.fixture()
    def registry(self, store, engine):
        return CapabilityRegistry(event_store=store, projection_engine=engine)

    @pytest.mark.asyncio
    async def test_register_emits_event(self, registry, store):
        cap = Capability(capability_id="search", agent_id="a1")
        await registry.register(cap)
        events = await store.read()
        assert len(events) == 1
        assert events[0].event_type == "capability.registered"

    @pytest.mark.asyncio
    async def test_register_and_get_state(self, registry):
        cap = Capability(capability_id="search", agent_id="a1", version="1.0.0")
        await registry.register(cap)
        state = await registry.get_state()
        assert "search@1.0.0" in state["capabilities"]

    @pytest.mark.asyncio
    async def test_deprecate(self, registry):
        cap = Capability(capability_id="old", agent_id="a1")
        await registry.register(cap)
        await registry.deprecate("old")
        state = await registry.get_state()
        assert "old@1.0.0" in state["deprecated"]

    @pytest.mark.asyncio
    async def test_register_multiple(self, registry):
        await registry.register(Capability(capability_id="c1", agent_id="a1"))
        await registry.register(Capability(capability_id="c2", agent_id="a2"))
        state = await registry.get_state()
        assert len(state["capabilities"]) == 2
