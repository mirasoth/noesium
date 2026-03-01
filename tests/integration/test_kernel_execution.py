"""Integration test: graph execution -> event store -> projection state."""

import pytest

from noesium.core.event.envelope import AgentRef
from noesium.core.event.store import InMemoryEventStore
from noesium.core.event.types import NodeCompleted, NodeEntered
from noesium.core.kernel.executor import KernelExecutor
from noesium.core.projection.base import ProjectionEngine
from noesium.core.projection.execution import ExecutionProjection


class _ThreeNodeGraph:
    """Fake 3-node graph that emits pending events via state."""

    async def ainvoke(self, state, config=None):
        pending = [
            NodeEntered(node_id="a", graph_id="test"),
            NodeCompleted(node_id="a", graph_id="test", duration_ms=10.0),
            NodeEntered(node_id="b", graph_id="test"),
            NodeCompleted(node_id="b", graph_id="test", duration_ms=20.0),
            NodeEntered(node_id="c", graph_id="test"),
            NodeCompleted(node_id="c", graph_id="test", duration_ms=30.0),
        ]
        return {
            **state,
            "result": "done",
            "_pending_events": pending,
        }


@pytest.mark.integration
class TestKernelExecution:
    @pytest.mark.asyncio
    async def test_full_execution_flow(self):
        store = InMemoryEventStore()
        producer = AgentRef(agent_id="int-agent", agent_type="test")
        graph = _ThreeNodeGraph()

        executor = KernelExecutor(graph=graph, event_store=store, producer=producer)
        result = await executor.execute({"input": "hello"})

        assert result["result"] == "done"

        events = await store.read()
        types = [e.event_type for e in events]

        assert types[0] == "agent.started"
        assert types[-1] == "agent.stopped"
        assert types.count("kernel.node.entered") == 3
        assert types.count("kernel.node.completed") == 3

    @pytest.mark.asyncio
    async def test_execution_feeds_projection(self):
        store = InMemoryEventStore()
        producer = AgentRef(agent_id="int-agent", agent_type="test")
        graph = _ThreeNodeGraph()
        engine = ProjectionEngine(event_store=store)
        engine.register("exec", ExecutionProjection())

        executor = KernelExecutor(graph=graph, event_store=store, producer=producer)
        await executor.execute({})

        state = await engine.get_state("exec")
        assert state["total_nodes_entered"] == 3
        assert state["total_nodes_completed"] == 3
        assert state["node_executions"]["a"]["total_ms"] == 10.0
        assert state["node_executions"]["c"]["total_ms"] == 30.0
