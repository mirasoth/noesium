"""Bridge between event-sourced EventEnvelope and bubus EventBus (RFC-1001 Section 6.4)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from bubus import BaseEvent, EventBus

from noesium.core.event.envelope import EventEnvelope
from noesium.core.event.store import EventStore

logger = logging.getLogger(__name__)


class EnvelopeEvent(BaseEvent[EventEnvelope]):
    """Bubus event wrapping an EventEnvelope for bus dispatch."""

    envelope: EventEnvelope

    def __init__(self, envelope: EventEnvelope, **kwargs: Any) -> None:
        super().__init__(data=envelope, envelope=envelope, **kwargs)


class EnvelopeBridge:
    """Stores envelopes to EventStore then publishes via bubus EventBus.

    Provides a subscribe interface that filters by event_type string
    and delivers the unwrapped EventEnvelope to the handler.
    """

    def __init__(self, event_store: EventStore, event_bus: EventBus) -> None:
        self._store = event_store
        self._bus = event_bus
        self._handlers: dict[str, list[Callable[[EventEnvelope], Awaitable[None]]]] = {}
        self._bus.on(EnvelopeEvent, self._dispatch)

    async def publish(self, envelope: EventEnvelope) -> None:
        """Persist envelope then emit on the bus."""
        await self._store.append(envelope)
        self._bus.dispatch(EnvelopeEvent(envelope=envelope))

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[EventEnvelope], Awaitable[None]],
    ) -> None:
        """Register a handler for a specific event_type string."""
        self._handlers.setdefault(event_type, []).append(handler)

    async def _dispatch(self, event: EnvelopeEvent) -> None:
        """Internal bubus handler that fans out to typed subscribers."""
        envelope = event.envelope
        handlers = self._handlers.get(envelope.event_type, [])
        for handler in handlers:
            try:
                await handler(envelope)
            except Exception:
                logger.exception(
                    "Handler %s failed for event_type=%s",
                    handler.__name__,
                    envelope.event_type,
                )
