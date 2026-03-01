"""Tests for DurableMemory."""

import pytest

from noesium.core.event.envelope import AgentRef
from noesium.core.event.store import InMemoryEventStore
from noesium.core.memory.durable import DurableMemory


class TestDurableMemory:
    @pytest.fixture()
    def store(self):
        return InMemoryEventStore()

    @pytest.fixture()
    def producer(self):
        return AgentRef(agent_id="mem-agent", agent_type="test")

    @pytest.fixture()
    def mem(self, store, producer):
        return DurableMemory(event_store=store, producer=producer)

    @pytest.mark.asyncio
    async def test_write_emits_event(self, mem, store):
        await mem.write("greeting", "hello")
        events = await store.read()
        assert len(events) == 1
        assert events[0].event_type == "memory.written"
        assert events[0].payload["key"] == "greeting"

    @pytest.mark.asyncio
    async def test_read_after_write(self, mem):
        await mem.write("x", 42)
        assert mem.read("x") == 42

    @pytest.mark.asyncio
    async def test_read_missing_returns_none(self, mem):
        assert mem.read("nope") is None

    @pytest.mark.asyncio
    async def test_auto_value_type(self, mem, store):
        await mem.write("k", [1, 2, 3])
        events = await store.read()
        assert events[0].payload["value_type"] == "list"

    @pytest.mark.asyncio
    async def test_rebuild(self, store, producer):
        mem1 = DurableMemory(event_store=store, producer=producer)
        await mem1.write("a", 1)
        await mem1.write("b", 2)

        mem2 = DurableMemory(event_store=store, producer=producer)
        assert mem2.read("a") is None
        await mem2.rebuild()
        assert mem2.read("a") == 1
        assert mem2.read("b") == 2
