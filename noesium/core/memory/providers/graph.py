"""Graph memory provider stub (RFC-2001 §10, RFC-2002 §6.4).

This provider is not yet implemented. All graph-specific operations raise
NotImplementedError. Standard MemoryProvider operations also raise.
"""

from __future__ import annotations

from typing import Any

from noesium.core.memory.provider import (
    MemoryEntry,
    MemoryProvider,
    MemoryTier,
    ProviderCapabilities,
    RecallResult,
)


class GraphMemoryProvider(MemoryProvider):
    """Stub for future graph-based memory."""

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id="graph",
            tier=MemoryTier.PERSISTENT,
            supports_search=True,
            supports_graph=True,
            content_types=["entity"],
        )

    async def write(
        self,
        key: str,
        value: Any,
        *,
        content_type: str = "fact",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        raise NotImplementedError("Graph memory provider is not yet implemented")

    async def read(self, key: str) -> MemoryEntry | None:
        raise NotImplementedError("Graph memory provider is not yet implemented")

    async def delete(self, key: str) -> bool:
        raise NotImplementedError("Graph memory provider is not yet implemented")

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        content_types: list[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[RecallResult]:
        raise NotImplementedError("Graph memory provider is not yet implemented")

    async def list_keys(
        self,
        *,
        content_types: list[str] | None = None,
        prefix: str | None = None,
    ) -> list[str]:
        raise NotImplementedError("Graph memory provider is not yet implemented")

    async def add_entity(self, entity_id: str, entity_type: str, properties: dict[str, Any]) -> MemoryEntry:
        raise NotImplementedError("Graph memory provider is not yet implemented")

    async def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError("Graph memory provider is not yet implemented")

    async def traverse(
        self,
        start_id: str,
        path_pattern: str | None = None,
        depth: int = 2,
    ) -> list[MemoryEntry]:
        raise NotImplementedError("Graph memory provider is not yet implemented")
