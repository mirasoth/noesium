"""Memory manager composing all three memory layers (RFC-1001 Section 9.4)."""

from __future__ import annotations

from typing import Any

from .durable import DurableMemory
from .ephemeral import EphemeralMemory
from .semantic_memory import SemanticMemory


class MemoryManager:
    """Unified interface over ephemeral, durable, and semantic memory.

    - ``store`` routes to the appropriate layer based on flags.
    - ``recall`` reads from durable first, falls back to ephemeral.
    - ``search`` delegates to semantic memory.
    """

    def __init__(
        self,
        ephemeral: EphemeralMemory | None = None,
        durable: DurableMemory | None = None,
        semantic: SemanticMemory | None = None,
    ) -> None:
        self._ephemeral = ephemeral or EphemeralMemory()
        self._durable = durable
        self._semantic = semantic

    async def store(
        self,
        key: str,
        value: Any,
        *,
        durable: bool = False,
        index: bool = False,
    ) -> None:
        """Store a value, optionally persisting and/or indexing it."""
        self._ephemeral.set(key, value)

        if durable and self._durable is not None:
            await self._durable.write(key, value)

        if index and self._semantic is not None:
            text = str(value)
            await self._semantic.index(key, text)

    def recall(self, key: str) -> Any | None:
        """Recall a value: durable first, then ephemeral."""
        if self._durable is not None:
            val = self._durable.read(key)
            if val is not None:
                return val
        return self._ephemeral.get(key)

    async def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Semantic search. Returns empty list if semantic layer unavailable."""
        if self._semantic is None:
            return []
        return await self._semantic.search(query, k=k)
