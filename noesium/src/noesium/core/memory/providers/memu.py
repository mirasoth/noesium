"""MemU file-based memory provider (RFC-2002 §6.3).

Wraps the existing MemuMemoryStore, emitting MemoryWritten events for observability.
"""

from __future__ import annotations

from typing import Any

from noesium.core.event.envelope import AgentRef, TraceContext
from noesium.core.event.store import EventStore
from noesium.core.event.types import MemoryWritten
from noesium.core.memory.models import MemoryItem, SearchResult
from noesium.core.memory.provider import (
    MemoryEntry,
    MemoryProvider,
    MemoryTier,
    ProviderCapabilities,
    RecallResult,
)


class MemuProvider(MemoryProvider):
    """Wraps MemuMemoryStore as a persistent, searchable provider."""

    def __init__(
        self,
        memory_store: Any,  # MemuMemoryStore (avoid hard import for optional dep)
        event_store: EventStore | None = None,
        producer: AgentRef | None = None,
    ) -> None:
        self._store = memory_store
        self._event_store = event_store
        self._producer = producer

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id="memu",
            tier=MemoryTier.PERSISTENT,
            supports_search=True,
            content_types=["activity", "profile", "event", "fact", "conversation"],
        )

    async def write(
        self,
        key: str,
        value: Any,
        *,
        content_type: str = "fact",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        item = MemoryItem(
            id=key,
            content=str(value),
            memory_type=content_type if content_type in ("message", "fact", "note") else "fact",
            metadata=metadata or {},
        )
        await self._store.add(item)

        if self._event_store and self._producer:
            event = MemoryWritten(
                key=key,
                value=value,
                value_type="text",
                content_type=content_type,
                provider_id="memu",
            )
            envelope = event.to_envelope(producer=self._producer, trace=TraceContext())
            await self._event_store.append(envelope)

        return MemoryEntry(
            key=key,
            value=value,
            content_type=content_type,
            metadata=metadata or {},
            provider_id="memu",
        )

    async def read(self, key: str) -> MemoryEntry | None:
        item = await self._store.get(key)
        if item is None:
            return None
        return MemoryEntry(
            key=item.id,
            value=item.content,
            content_type=item.memory_type,
            provider_id="memu",
        )

    async def delete(self, key: str) -> bool:
        try:
            await self._store.delete(key)
            return True
        except Exception:
            return False

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        content_types: list[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[RecallResult]:
        results: list[SearchResult] = await self._store.search(query=query, limit=limit)
        return [
            RecallResult(
                entry=MemoryEntry(
                    key=r.memory_item.id,
                    value=r.memory_item.content,
                    content_type=r.memory_item.memory_type,
                    provider_id="memu",
                ),
                score=r.relevance_score,
                provider_id="memu",
                tier=MemoryTier.PERSISTENT,
            )
            for r in results
        ]

    async def list_keys(
        self,
        *,
        content_types: list[str] | None = None,
        prefix: str | None = None,
    ) -> list[str]:
        all_items = await self._store.list()
        keys = [item.id for item in all_items]
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        return keys
