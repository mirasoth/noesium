"""Tests for MemoryManager."""

import pytest

from noesium.core.event.envelope import AgentRef
from noesium.core.event.store import InMemoryEventStore
from noesium.core.memory.durable import DurableMemory
from noesium.core.memory.ephemeral import EphemeralMemory
from noesium.core.memory.manager import MemoryManager


class TestMemoryManager:
    @pytest.fixture()
    def ephemeral(self):
        return EphemeralMemory()

    @pytest.fixture()
    def store(self):
        return InMemoryEventStore()

    @pytest.fixture()
    def durable(self, store):
        return DurableMemory(
            event_store=store,
            producer=AgentRef(agent_id="mgr", agent_type="test"),
        )

    @pytest.fixture()
    def manager(self, ephemeral, durable):
        return MemoryManager(ephemeral=ephemeral, durable=durable)

    @pytest.mark.asyncio
    async def test_store_ephemeral_only(self, manager, ephemeral):
        await manager.store("k", "v")
        assert ephemeral.get("k") == "v"

    @pytest.mark.asyncio
    async def test_store_durable(self, manager, store):
        await manager.store("k", "v", durable=True)
        events = await store.read()
        assert len(events) == 1
        assert events[0].event_type == "memory.written"

    @pytest.mark.asyncio
    async def test_recall_prefers_durable(self, manager):
        await manager.store("k", "durable_val", durable=True)
        manager._ephemeral.set("k", "ephemeral_val")
        assert manager.recall("k") == "durable_val"

    @pytest.mark.asyncio
    async def test_recall_falls_back_to_ephemeral(self, manager):
        await manager.store("k", "eph")
        assert manager.recall("k") == "eph"

    @pytest.mark.asyncio
    async def test_recall_missing(self, manager):
        assert manager.recall("nope") is None

    @pytest.mark.asyncio
    async def test_search_without_semantic(self, manager):
        results = await manager.search("anything")
        assert results == []

    @pytest.mark.asyncio
    async def test_ephemeral_only_manager(self):
        mgr = MemoryManager()
        await mgr.store("x", 1)
        assert mgr.recall("x") == 1
