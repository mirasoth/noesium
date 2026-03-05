"""Memory provider abstraction and core types (RFC-2001 §6, RFC-2002 §4-5)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MemoryTier(str, Enum):
    WORKING = "working"
    PERSISTENT = "persistent"
    INDEXED = "indexed"


class ProviderCapabilities(BaseModel):
    provider_id: str
    tier: MemoryTier
    supports_search: bool = False
    supports_graph: bool = False
    content_types: list[str] = Field(default_factory=lambda: ["*"])
    read_only: bool = False


class MemoryEntry(BaseModel):
    key: str
    value: Any
    content_type: str = "fact"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime | None = None
    ttl_ms: int | None = None
    provider_id: str | None = None


class RecallScope(str, Enum):
    WORKING = "working"
    PERSISTENT = "persistent"
    INDEXED = "indexed"
    ALL = "all"


class RecallQuery(BaseModel):
    query: str
    scope: RecallScope = RecallScope.ALL
    content_types: list[str] | None = None
    provider_ids: list[str] | None = None
    limit: int = 10
    metadata_filters: dict[str, Any] = Field(default_factory=dict)


class RecallResult(BaseModel):
    entry: MemoryEntry
    score: float = 1.0
    provider_id: str
    tier: MemoryTier


class MemoryProvider(ABC):
    """Abstract base for all memory providers (RFC-2001 §6.1)."""

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...

    @abstractmethod
    async def write(
        self,
        key: str,
        value: Any,
        *,
        content_type: str = "fact",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry: ...

    @abstractmethod
    async def read(self, key: str) -> MemoryEntry | None: ...

    @abstractmethod
    async def delete(self, key: str) -> bool: ...

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        content_types: list[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[RecallResult]: ...

    @abstractmethod
    async def list_keys(
        self,
        *,
        content_types: list[str] | None = None,
        prefix: str | None = None,
    ) -> list[str]: ...

    async def rebuild(self) -> None:
        """Rebuild derived state. No-op by default."""

    async def close(self) -> None:
        """Release resources. No-op by default."""
