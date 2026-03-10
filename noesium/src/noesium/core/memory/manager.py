"""Memory manager composing all three memory layers (RFC-1001 Section 9.4)."""

from __future__ import annotations

from typing import Any

from .ephemeral import EphemeralMemory
from .semantic_memory import SemanticMemory


class MemoryManager:
    """Unified interface over ephemeral and semantic memory.

    - ``store`` routes to the appropriate layer based on flags.
    - ``recall`` reads from ephemeral memory.
    - ``search`` delegates to semantic memory.
    """

    def __init__(
        self,
        ephemeral: EphemeralMemory | None = None,
        semantic: SemanticMemory | None = None,
    ) -> None:
        self._ephemeral = ephemeral or EphemeralMemory()
        self._semantic = semantic

    async def store(
        self,
        key: str,
        value: Any,
        *,
        index: bool = False,
    ) -> None:
        """Store a value, optionally indexing it for semantic search."""
        self._ephemeral.set(key, value)

        if index and self._semantic is not None:
            text = str(value)
            await self._semantic.index(key, text)

    def recall(self, key: str) -> Any | None:
        """Recall a value from ephemeral memory."""
        return self._ephemeral.get(key)

    async def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Semantic search. Returns empty list if semantic layer unavailable."""
        if self._semantic is None:
            return []
        return await self._semantic.search(query, k=k)
