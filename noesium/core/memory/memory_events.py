"""Extended memory domain events (RFC-2002 §7).

MemoryWritten lives in noesium.core.event.types for backward compatibility.
This module adds the remaining memory lifecycle events.
"""

from __future__ import annotations

from typing import Any

from noesium.core.event.types import DomainEvent


class MemoryDeleted(DomainEvent):
    key: str
    provider_id: str = ""

    def event_type(self) -> str:
        return "memory.deleted"


class MemoryLinked(DomainEvent):
    source_key: str
    target_key: str
    relation: str

    def event_type(self) -> str:
        return "memory.linked"


class MemoryProviderRegistered(DomainEvent):
    provider_id: str
    tier: str
    capabilities: dict[str, Any]

    def event_type(self) -> str:
        return "memory.provider.registered"
