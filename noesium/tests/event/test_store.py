"""Tests for InMemoryEventStore and FileEventStore."""

import pytest

from noesium.core.event.envelope import AgentRef, EventEnvelope, TraceContext
from noesium.core.event.store import FileEventStore, InMemoryEventStore


def _make_envelope(event_type: str = "test.event", correlation_id: str | None = None) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        producer=AgentRef(agent_id="a1", agent_type="test"),
        trace=TraceContext(),
        correlation_id=correlation_id,
        payload={"data": event_type},
    )


class TestInMemoryEventStore:
    @pytest.fixture()
    def store(self):
        return InMemoryEventStore()

    @pytest.mark.asyncio
    async def test_append_and_read(self, store):
        env = _make_envelope()
        await store.append(env)
        events = await store.read()
        assert len(events) == 1
        assert events[0].event_id == env.event_id

    @pytest.mark.asyncio
    async def test_last_offset(self, store):
        assert await store.last_offset() == 0
        await store.append(_make_envelope())
        await store.append(_make_envelope())
        assert await store.last_offset() == 2

    @pytest.mark.asyncio
    async def test_read_with_offset(self, store):
        for i in range(5):
            await store.append(_make_envelope(f"type.{i}"))
        events = await store.read(from_offset=3)
        assert len(events) == 2
        assert events[0].event_type == "type.3"

    @pytest.mark.asyncio
    async def test_read_with_limit(self, store):
        for i in range(5):
            await store.append(_make_envelope())
        events = await store.read(limit=2)
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_read_by_event_type(self, store):
        await store.append(_make_envelope("a"))
        await store.append(_make_envelope("b"))
        await store.append(_make_envelope("a"))
        events = await store.read(event_type="a")
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_read_by_correlation(self, store):
        await store.append(_make_envelope(correlation_id="c1"))
        await store.append(_make_envelope(correlation_id="c2"))
        await store.append(_make_envelope(correlation_id="c1"))
        events = await store.read_by_correlation("c1")
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_combined_filters(self, store):
        await store.append(_make_envelope("a", correlation_id="c1"))
        await store.append(_make_envelope("b", correlation_id="c1"))
        await store.append(_make_envelope("a", correlation_id="c2"))
        events = await store.read(event_type="a", correlation_id="c1")
        assert len(events) == 1


class TestFileEventStore:
    @pytest.fixture()
    def store(self, tmp_path):
        return FileEventStore(tmp_path / "events.jsonl")

    @pytest.mark.asyncio
    async def test_append_and_read(self, store):
        env = _make_envelope()
        await store.append(env)
        events = await store.read()
        assert len(events) == 1
        assert events[0].event_id == env.event_id

    @pytest.mark.asyncio
    async def test_last_offset(self, store):
        assert await store.last_offset() == 0
        await store.append(_make_envelope())
        await store.append(_make_envelope())
        assert await store.last_offset() == 2

    @pytest.mark.asyncio
    async def test_read_with_offset(self, store):
        for i in range(5):
            await store.append(_make_envelope(f"type.{i}"))
        events = await store.read(from_offset=3)
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_read_by_event_type(self, store):
        await store.append(_make_envelope("a"))
        await store.append(_make_envelope("b"))
        events = await store.read(event_type="a")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_read_by_correlation(self, store):
        await store.append(_make_envelope(correlation_id="c1"))
        await store.append(_make_envelope(correlation_id="c2"))
        events = await store.read_by_correlation("c1")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_persistence_across_instances(self, tmp_path):
        path = tmp_path / "events.jsonl"
        store1 = FileEventStore(path)
        await store1.append(_make_envelope())
        store2 = FileEventStore(path)
        events = await store2.read()
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_empty_file(self, tmp_path):
        store = FileEventStore(tmp_path / "empty.jsonl")
        events = await store.read()
        assert events == []
