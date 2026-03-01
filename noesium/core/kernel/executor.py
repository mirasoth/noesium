"""KernelExecutor: event-sourced wrapper around LangGraph graphs (RFC-1001 Section 7)."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from noesium.core.event.envelope import AgentRef, TraceContext
from noesium.core.event.store import EventStore
from noesium.core.event.types import AgentStarted, AgentStopped, DomainEvent
from noesium.core.exceptions import KernelError, NodeExecutionError
from noesium.core.msgbus.bridge import EnvelopeBridge

logger = logging.getLogger(__name__)


class NodeResult(BaseModel):
    """Result returned by a kernel node containing a state delta and events."""

    state_delta: dict[str, Any] = Field(default_factory=dict)
    events: list[DomainEvent] = Field(default_factory=list)


class KernelExecutor:
    """Wraps a LangGraph ``CompiledStateGraph`` with event-sourced execution.

    On each ``execute`` call the executor:
    1. Emits ``AgentStarted``.
    2. Invokes the graph.
    3. Collects ``_pending_events`` from the final state.
    4. Emits each pending event + ``AgentStopped``.
    """

    def __init__(
        self,
        graph: Any,
        event_store: EventStore,
        producer: AgentRef,
        bridge: EnvelopeBridge | None = None,
    ) -> None:
        self._graph = graph
        self._event_store = event_store
        self._producer = producer
        self._bridge = bridge
        self._trace = TraceContext()

    async def execute(
        self,
        initial_state: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the graph and emit lifecycle events."""
        started = AgentStarted(
            agent_id=self._producer.agent_id,
            agent_type=self._producer.agent_type,
        )
        await self._emit(started)

        try:
            result = await self._invoke_graph(initial_state, config)
        except Exception as exc:
            stopped = AgentStopped(
                agent_id=self._producer.agent_id,
                reason=f"error: {exc}",
            )
            await self._emit(stopped)
            raise KernelError(str(exc)) from exc

        pending: list[DomainEvent] = result.pop("_pending_events", []) or []
        for event in pending:
            await self._emit(event)

        stopped = AgentStopped(
            agent_id=self._producer.agent_id,
            reason="completed",
        )
        await self._emit(stopped)
        return result

    async def _invoke_graph(
        self,
        initial_state: dict[str, Any],
        config: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Invoke the underlying LangGraph graph."""
        try:
            result = await self._graph.ainvoke(initial_state, config=config)
        except AttributeError:
            result = self._graph.invoke(initial_state, config=config)
        if not isinstance(result, dict):
            raise NodeExecutionError(f"Graph must return dict, got {type(result)}")
        return result

    async def _emit(self, event: DomainEvent) -> None:
        """Convert domain event to envelope and persist + publish."""
        envelope = event.to_envelope(
            producer=self._producer,
            trace=self._trace,
        )
        await self._event_store.append(envelope)
        if self._bridge:
            await self._bridge.publish(envelope)
