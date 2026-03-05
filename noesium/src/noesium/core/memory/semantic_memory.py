"""Semantic memory with vector search (RFC-1001 Section 9.3)."""

from __future__ import annotations

from typing import Any

from .durable import DurableMemory


class SemanticMemory:
    """Wraps DurableMemory + optional vector store + optional LLM client.

    Provides ``index`` and ``search`` operations on top of durable memory.
    Real vector-store integration is deferred -- this layer accepts any object
    implementing ``async def add_texts(texts, metadatas)`` and
    ``async def similarity_search(query, k)`` (i.e. LangChain vector-store
    compatible or Noesium ``BaseVectorStore``).
    """

    def __init__(
        self,
        durable: DurableMemory,
        vector_store: Any | None = None,
        llm_client: Any | None = None,
    ) -> None:
        self._durable = durable
        self._vector_store = vector_store
        self._llm = llm_client

    async def index(self, key: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Write to durable memory and optionally index into vector store."""
        await self._durable.write(key, text, value_type="text")
        if self._vector_store is not None:
            await self._vector_store.add_texts(
                texts=[text],
                metadatas=[{"key": key, **(metadata or {})}],
            )

    async def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Search the vector store. Returns empty list if no store configured."""
        if self._vector_store is None:
            return []
        results = await self._vector_store.similarity_search(query, k=k)
        return [
            {"content": r.page_content, "metadata": r.metadata} if hasattr(r, "page_content") else r for r in results
        ]

    async def rebuild_index(self) -> None:
        """Rebuild durable state and optionally re-index."""
        await self._durable.rebuild()
