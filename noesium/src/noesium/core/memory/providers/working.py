"""Working (ephemeral) memory provider -- dict-backed, no IO (RFC-2002 §6.1)."""

from __future__ import annotations

from typing import Any

from noesium.core.memory.provider import (
    MemoryEntry,
    MemoryProvider,
    MemoryTier,
    ProviderCapabilities,
    RecallResult,
)


class WorkingMemoryProvider(MemoryProvider):
    """In-process dict storage. Session-scoped, cleared on restart."""

    def __init__(self) -> None:
        self._data: dict[str, MemoryEntry] = {}

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id="working",
            tier=MemoryTier.WORKING,
            supports_search=True,
        )

    async def write(
        self,
        key: str,
        value: Any,
        *,
        content_type: str = "fact",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            key=key,
            value=value,
            content_type=content_type,
            metadata=metadata or {},
            provider_id="working",
        )
        self._data[key] = entry
        return entry

    async def read(self, key: str) -> MemoryEntry | None:
        return self._data.get(key)

    async def delete(self, key: str) -> bool:
        return self._data.pop(key, None) is not None

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
        for entry in self._data.values():
            if content_types and entry.content_type not in content_types:
                continue
            if query_lower in str(entry.value).lower():
                results.append(
                    RecallResult(
                        entry=entry,
                        score=1.0,
                        provider_id="working",
                        tier=MemoryTier.WORKING,
                    )
                )
        return results[:limit]

    async def list_keys(
        self,
        *,
        content_types: list[str] | None = None,
        prefix: str | None = None,
    ) -> list[str]:
        keys = list(self._data.keys())
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        if content_types:
            keys = [k for k in keys if self._data[k].content_type in content_types]
        return keys
