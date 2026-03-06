"""Event store implementations (RFC-1001 Section 6.3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from noesium.core.exceptions import EventStoreError

from .envelope import EventEnvelope


class EventStore(ABC):
    """Append-only event log per agent."""

    @abstractmethod
    async def append(self, envelope: EventEnvelope) -> None: ...

    @abstractmethod
    async def read(
        self,
        from_offset: int = 0,
        limit: int | None = None,
        event_type: str | None = None,
        correlation_id: str | None = None,
    ) -> list[EventEnvelope]: ...

    @abstractmethod
    async def last_offset(self) -> int: ...

    @abstractmethod
    async def read_by_correlation(self, correlation_id: str) -> list[EventEnvelope]: ...


class InMemoryEventStore(EventStore):
    """List-backed event store for testing and development."""

    def __init__(self) -> None:
        self._events: list[EventEnvelope] = []

    async def append(self, envelope: EventEnvelope) -> None:
        self._events.append(envelope)

    async def read(
        self,
        from_offset: int = 0,
        limit: int | None = None,
        event_type: str | None = None,
        correlation_id: str | None = None,
    ) -> list[EventEnvelope]:
        events = self._events[from_offset:]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if correlation_id:
            events = [e for e in events if e.correlation_id == correlation_id]
        if limit:
            events = events[:limit]
        return events

    async def last_offset(self) -> int:
        return len(self._events)

    async def read_by_correlation(self, correlation_id: str) -> list[EventEnvelope]:
        return [e for e in self._events if e.correlation_id == correlation_id]


class FileEventStore(EventStore):
    """JSONL file-backed event store for single-process persistence."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    async def append(self, envelope: EventEnvelope) -> None:
        try:
            with open(self._path, "a") as f:
                f.write(envelope.model_dump_json() + "\n")
        except OSError as exc:
            raise EventStoreError(f"Failed to append event: {exc}") from exc

    async def read(
        self,
        from_offset: int = 0,
        limit: int | None = None,
        event_type: str | None = None,
        correlation_id: str | None = None,
    ) -> list[EventEnvelope]:
        if not self._path.exists():
            return []
        events: list[EventEnvelope] = []
        try:
            with open(self._path) as f:
                for i, line in enumerate(f):
                    if i < from_offset:
                        continue
                    stripped = line.strip()
                    if not stripped:
                        continue
                    envelope = EventEnvelope.model_validate_json(stripped)
                    if event_type and envelope.event_type != event_type:
                        continue
                    if correlation_id and envelope.correlation_id != correlation_id:
                        continue
                    events.append(envelope)
                    if limit and len(events) >= limit:
                        break
        except OSError as exc:
            raise EventStoreError(f"Failed to read events: {exc}") from exc
        return events

    async def last_offset(self) -> int:
        if not self._path.exists():
            return 0
        with open(self._path) as f:
            return sum(1 for line in f if line.strip())

    async def read_by_correlation(self, correlation_id: str) -> list[EventEnvelope]:
        return await self.read(correlation_id=correlation_id)
