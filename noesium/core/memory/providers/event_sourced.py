"""Event-sourced persistent memory provider (RFC-2002 §6.2).

Wraps EventStore + CognitiveProjection. All writes emit MemoryWritten events.
"""

from __future__ import annotations

from typing import Any

from noesium.core.event.envelope import AgentRef, TraceContext
from noesium.core.event.store import EventStore
from noesium.core.event.types import MemoryWritten
from noesium.core.memory.provider import (
    MemoryEntry,
    MemoryProvider,
    MemoryTier,
    ProviderCapabilities,
    RecallResult,
)
from noesium.core.msgbus.bridge import EnvelopeBridge
from noesium.core.projection.cognitive import CognitiveProjection


class EventSourcedProvider(MemoryProvider):
    """Wraps EventStore + CognitiveProjection for persistent memory."""

    def __init__(
        self,
        event_store: EventStore,
        producer: AgentRef,
        projection: CognitiveProjection | None = None,
        bridge: EnvelopeBridge | None = None,
    ) -> None:
        self._store = event_store
        self._producer = producer
        self._projection = projection or CognitiveProjection()
        self._bridge = bridge
        self._trace = TraceContext()
        self._state = self._projection.initial_state()

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id="event_sourced",
            tier=MemoryTier.PERSISTENT,
            supports_search=False,
        )

    async def write(
        self,
        key: str,
        value: Any,
        *,
        content_type: str = "fact",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        event = MemoryWritten(
            key=key,
            value=value,
            value_type=type(value).__name__,
            content_type=content_type,
            provider_id="event_sourced",
        )
        envelope = event.to_envelope(producer=self._producer, trace=self._trace)
        await self._store.append(envelope)
        if self._bridge:
            await self._bridge.publish(envelope)
        self._state = self._projection.apply(self._state, envelope)
        return MemoryEntry(
            key=key,
            value=value,
            content_type=content_type,
            metadata=metadata or {},
            provider_id="event_sourced",
        )

    async def read(self, key: str) -> MemoryEntry | None:
        raw = self._state.get("memory_entries", {}).get(key)
        if raw is None:
            return None
        return MemoryEntry(
            key=key,
            value=raw["value"],
            content_type=raw.get("content_type", "fact"),
            provider_id="event_sourced",
        )

    async def delete(self, key: str) -> bool:
        entries = self._state.get("memory_entries", {})
        if key in entries:
            del entries[key]
            return True
        return False

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        content_types: list[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[RecallResult]:
        results: list[RecallResult] = []
        query_lower = query.lower()
        for key, raw in self._state.get("memory_entries", {}).items():
            ct = raw.get("content_type", "fact")
            if content_types and ct not in content_types:
                continue
            val = str(raw.get("value", ""))
            if query_lower in val.lower():
                results.append(
                    RecallResult(
                        entry=MemoryEntry(key=key, value=raw["value"], content_type=ct, provider_id="event_sourced"),
                        score=0.5,
                        provider_id="event_sourced",
                        tier=MemoryTier.PERSISTENT,
                    )
                )
        return results[:limit]

    async def list_keys(
        self,
        *,
        content_types: list[str] | None = None,
        prefix: str | None = None,
    ) -> list[str]:
        entries = self._state.get("memory_entries", {})
        keys = list(entries.keys())
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        if content_types:
            keys = [k for k in keys if entries[k].get("content_type", "fact") in content_types]
        return keys

    async def rebuild(self) -> None:
        events = await self._store.read(event_type="memory.written")
        self._state = self._projection.fold(events)
