"""Tests for CheckpointManager."""

import pytest

from noesium.core.event.envelope import AgentRef
from noesium.core.event.store import InMemoryEventStore
from noesium.core.exceptions import CheckpointError
from noesium.core.kernel.checkpoint import CheckpointManager


class TestCheckpointManager:
    @pytest.fixture()
    def store(self):
        return InMemoryEventStore()

    @pytest.fixture()
    def producer(self):
        return AgentRef(agent_id="cp-agent", agent_type="test")

    @pytest.mark.asyncio
    async def test_save_emits_checkpoint_created(self, store, producer):
        mgr = CheckpointManager(saver=None, event_store=store, producer=producer)
        await mgr.save(checkpoint_id="cp-1", node_id="node-a")

        events = await store.read()
        assert len(events) == 1
        assert events[0].event_type == "kernel.checkpoint.created"
        assert events[0].payload["checkpoint_id"] == "cp-1"
        assert events[0].payload["node_id"] == "node-a"

    @pytest.mark.asyncio
    async def test_load_returns_none_without_saver(self, store, producer):
        mgr = CheckpointManager(saver=None, event_store=store, producer=producer)
        result = await mgr.load()
        assert result is None

    @pytest.mark.asyncio
    async def test_replay_from_returns_checkpoint_events(self, store, producer):
        mgr = CheckpointManager(saver=None, event_store=store, producer=producer)
        await mgr.save(checkpoint_id="cp-1", node_id="n1")
        await mgr.save(checkpoint_id="cp-2", node_id="n2")

        replayed = await mgr.replay_from()
        assert len(replayed) == 2
        assert replayed[0].payload["checkpoint_id"] == "cp-1"
        assert replayed[1].payload["checkpoint_id"] == "cp-2"

    @pytest.mark.asyncio
    async def test_save_with_failing_saver(self, store, producer):
        class FailingSaver:
            def put(self, *args, **kwargs):
                raise RuntimeError("disk full")

        mgr = CheckpointManager(saver=FailingSaver(), event_store=store, producer=producer)
        with pytest.raises(CheckpointError, match="disk full"):
            await mgr.save(checkpoint_id="cp-1", node_id="n1", checkpoint_data={"state": {}})
