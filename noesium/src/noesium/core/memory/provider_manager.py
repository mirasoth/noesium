"""Provider-based memory manager facade (RFC-2002 §8).

This is the new unified memory manager that routes operations to registered
providers. The original MemoryManager in manager.py is preserved for backward
compatibility.
"""

from __future__ import annotations

from typing import Any

from noesium.core.exceptions import ProviderNotFoundError

from .provider import (
    MemoryEntry,
    MemoryProvider,
    MemoryTier,
    RecallQuery,
    RecallResult,
    RecallScope,
)
from .recall import merge_results


class ProviderMemoryManager:
    """Routes memory operations to registered providers.

    Unlike the legacy MemoryManager (which directly composes EphemeralMemory,
    DurableMemory, SemanticMemory), this facade is provider-agnostic.
    """

    def __init__(
        self,
        providers: list[MemoryProvider] | None = None,
    ) -> None:
        self._providers: dict[str, MemoryProvider] = {}
        for p in providers or []:
            self.register_provider(p)

    def register_provider(self, provider: MemoryProvider) -> None:
        caps = provider.capabilities()
        self._providers[caps.provider_id] = provider

    def get_provider(self, provider_id: str) -> MemoryProvider:
        if provider_id not in self._providers:
            raise ProviderNotFoundError(f"Provider '{provider_id}' is not registered")
        return self._providers[provider_id]

    def providers_by_tier(self, tier: MemoryTier) -> list[MemoryProvider]:
        return [p for p in self._providers.values() if p.capabilities().tier == tier]

    async def store(
        self,
        key: str,
        value: Any,
        *,
        content_type: str = "fact",
        tier: MemoryTier = MemoryTier.WORKING,
        provider_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        if provider_id:
            provider = self.get_provider(provider_id)
        else:
            candidates = self.providers_by_tier(tier)
            if not candidates:
                raise ProviderNotFoundError(f"No provider registered for tier {tier.value}")
            provider = candidates[0]
        return await provider.write(key, value, content_type=content_type, metadata=metadata)

    async def recall(self, query: RecallQuery) -> list[RecallResult]:
        """Unified recall across providers (RFC-2001 §9)."""
        all_results: list[RecallResult] = []
        for provider in self._providers.values():
            caps = provider.capabilities()
            if query.scope != RecallScope.ALL and caps.tier.value != query.scope.value:
                continue
            if query.provider_ids and caps.provider_id not in query.provider_ids:
                continue
            try:
                results = await provider.search(
                    query.query,
                    limit=query.limit,
                    content_types=query.content_types,
                    metadata_filters=query.metadata_filters or None,
                )
                all_results.extend(results)
            except NotImplementedError:
                continue
        return merge_results(all_results, limit=query.limit)

    async def read(self, key: str, provider_id: str | None = None) -> MemoryEntry | None:
        if provider_id:
            return await self.get_provider(provider_id).read(key)
        for tier in [MemoryTier.WORKING, MemoryTier.PERSISTENT, MemoryTier.INDEXED]:
            for provider in self.providers_by_tier(tier):
                entry = await provider.read(key)
                if entry is not None:
                    return entry
        return None

    async def delete(self, key: str, provider_id: str | None = None) -> bool:
        if provider_id:
            return await self.get_provider(provider_id).delete(key)
        for provider in self._providers.values():
            if await provider.delete(key):
                return True
        return False

    async def close(self) -> None:
        for provider in self._providers.values():
            await provider.close()
