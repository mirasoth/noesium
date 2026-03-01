"""Base projection and projection engine (RFC-1001 Section 8)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from noesium.core.event.envelope import EventEnvelope
from noesium.core.event.store import EventStore

TState = TypeVar("TState")


class BaseProjection(ABC, Generic[TState]):
    """A deterministic function over an event stream producing typed state."""

    @abstractmethod
    def initial_state(self) -> TState: ...

    @abstractmethod
    def apply(self, state: TState, event: EventEnvelope) -> TState: ...

    def fold(self, events: list[EventEnvelope]) -> TState:
        """Replay a list of events from initial state."""
        state = self.initial_state()
        for event in events:
            state = self.apply(state, event)
        return state


class ProjectionEngine:
    """Manages multiple projections over a shared event store.

    Tracks the last-applied offset per projection for incremental updates.
    """

    def __init__(self, event_store: EventStore) -> None:
        self._store = event_store
        self._projections: dict[str, BaseProjection[Any]] = {}
        self._states: dict[str, Any] = {}
        self._offsets: dict[str, int] = {}

    def register(self, name: str, projection: BaseProjection[Any]) -> None:
        """Register a projection by name."""
        self._projections[name] = projection
        self._states[name] = projection.initial_state()
        self._offsets[name] = 0

    async def get_state(self, name: str) -> Any:
        """Incrementally apply new events since last offset."""
        projection = self._projections[name]
        current_offset = self._offsets[name]
        events = await self._store.read(from_offset=current_offset)
        state = self._states[name]
        for event in events:
            state = projection.apply(state, event)
        self._states[name] = state
        self._offsets[name] = current_offset + len(events)
        return state

    async def rebuild(self, name: str) -> Any:
        """Full replay from offset 0."""
        projection = self._projections[name]
        events = await self._store.read()
        state = projection.fold(events)
        self._states[name] = state
        self._offsets[name] = len(events)
        return state

    async def apply_event(self, envelope: EventEnvelope) -> None:
        """Apply a single event to all registered projections."""
        for name, projection in self._projections.items():
            self._states[name] = projection.apply(self._states[name], envelope)
            self._offsets[name] += 1
