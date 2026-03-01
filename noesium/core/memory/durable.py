"""Durable event-sourced memory (RFC-1001 Section 9.2)."""

from __future__ import annotations

from typing import Any

from noesium.core.event.envelope import AgentRef, TraceContext
from noesium.core.event.store import EventStore
from noesium.core.event.types import MemoryWritten
from noesium.core.projection.cognitive import CognitiveProjection


class DurableMemory:
    """Wraps EventStore + CognitiveProjection for persistent memory.

    Writes emit ``MemoryWritten`` events; reads derive state from the projection.
    """

    def __init__(
        self,
        event_store: EventStore,
        producer: AgentRef,
        projection: CognitiveProjection | None = None,
    ) -> None:
        self._store = event_store
        self._producer = producer
        self._projection = projection or CognitiveProjection()
        self._trace = TraceContext()
        self._state = self._projection.initial_state()

    async def write(self, key: str, value: Any, value_type: str = "auto") -> None:
        """Persist a memory entry via event emission."""
        if value_type == "auto":
            value_type = type(value).__name__
        event = MemoryWritten(key=key, value=value, value_type=value_type)
        envelope = event.to_envelope(producer=self._producer, trace=self._trace)
        await self._store.append(envelope)
        self._state = self._projection.apply(self._state, envelope)

    def read(self, key: str) -> Any | None:
        """Read the latest value for *key* from projection state."""
        entry = self._state.get("memory_entries", {}).get(key)
        return entry["value"] if entry else None

    async def rebuild(self) -> None:
        """Full replay from event store."""
        events = await self._store.read(event_type="memory.written")
        self._state = self._projection.fold(events)
