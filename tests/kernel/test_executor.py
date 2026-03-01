"""Tests for KernelExecutor."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from noesium.core.event.envelope import AgentRef
from noesium.core.event.store import InMemoryEventStore
from noesium.core.event.types import NodeEntered
from noesium.core.exceptions import KernelError
from noesium.core.kernel.executor import KernelExecutor


def _make_producer() -> AgentRef:
    return AgentRef(agent_id="test-agent", agent_type="test")


class _FakeGraph:
    """Minimal LangGraph-compatible fake that returns state + optional pending events."""

    def __init__(self, output: dict, raise_error: Exception | None = None):
        self._output = output
        self._error = raise_error

    async def ainvoke(self, state, config=None):
        if self._error:
            raise self._error
        merged = {**state, **self._output}
        return merged


class TestKernelExecutor:
    @pytest.fixture()
    def store(self):
        return InMemoryEventStore()

    @pytest.fixture()
    def producer(self):
        return _make_producer()

    @pytest.mark.asyncio
    async def test_execute_emits_started_and_stopped(self, store, producer):
        graph = _FakeGraph({"result": "ok"})
        executor = KernelExecutor(graph=graph, event_store=store, producer=producer)

        result = await executor.execute({"input": "hello"})

        assert result["result"] == "ok"
        events = await store.read()
        types = [e.event_type for e in events]
        assert types[0] == "agent.started"
        assert types[-1] == "agent.stopped"

    @pytest.mark.asyncio
    async def test_execute_collects_pending_events(self, store, producer):
        pending = [NodeEntered(node_id="n1", graph_id="g1")]
        graph = _FakeGraph({"_pending_events": pending, "data": 42})
        executor = KernelExecutor(graph=graph, event_store=store, producer=producer)

        result = await executor.execute({})

        assert "_pending_events" not in result
        assert result["data"] == 42
        events = await store.read()
        types = [e.event_type for e in events]
        assert "kernel.node.entered" in types

    @pytest.mark.asyncio
    async def test_execute_on_error_emits_stopped_with_error(self, store, producer):
        graph = _FakeGraph({}, raise_error=RuntimeError("boom"))
        executor = KernelExecutor(graph=graph, event_store=store, producer=producer)

        with pytest.raises(KernelError, match="boom"):
            await executor.execute({})

        events = await store.read()
        types = [e.event_type for e in events]
        assert "agent.started" in types
        assert "agent.stopped" in types
        stopped_payload = events[-1].payload
        assert "error" in stopped_payload.get("reason", "")

    @pytest.mark.asyncio
    async def test_execute_without_bridge(self, store, producer):
        graph = _FakeGraph({"value": 1})
        executor = KernelExecutor(graph=graph, event_store=store, producer=producer, bridge=None)

        result = await executor.execute({})
        assert result["value"] == 1
        events = await store.read()
        assert len(events) >= 2

    @pytest.mark.asyncio
    async def test_execute_with_bridge_publishes(self, store, producer):
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        graph = _FakeGraph({"ok": True})
        executor = KernelExecutor(graph=graph, event_store=store, producer=producer, bridge=bridge)

        await executor.execute({})
        assert bridge.publish.await_count >= 2
