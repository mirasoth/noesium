"""Checkpoint manager with event emission (RFC-1001 Section 7)."""

from __future__ import annotations

import logging
from typing import Any

from noesium.core.event.envelope import AgentRef, EventEnvelope, TraceContext
from noesium.core.event.store import EventStore
from noesium.core.event.types import CheckpointCreated
from noesium.core.exceptions import CheckpointError

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages checkpoints via a LangGraph ``BaseCheckpointSaver`` and emits events."""

    def __init__(
        self,
        saver: Any,
        event_store: EventStore,
        producer: AgentRef,
    ) -> None:
        self._saver = saver
        self._event_store = event_store
        self._producer = producer
        self._trace = TraceContext()

    async def save(
        self,
        checkpoint_id: str,
        node_id: str,
        config: dict[str, Any] | None = None,
        checkpoint_data: dict[str, Any] | None = None,
    ) -> None:
        """Persist checkpoint and emit ``CheckpointCreated``."""
        try:
            if self._saver is not None and checkpoint_data is not None:
                self._saver.put(config or {}, checkpoint_data, {}, {})
        except Exception as exc:
            raise CheckpointError(f"Failed to save checkpoint: {exc}") from exc

        event = CheckpointCreated(checkpoint_id=checkpoint_id, node_id=node_id)
        envelope = event.to_envelope(producer=self._producer, trace=self._trace)
        await self._event_store.append(envelope)

    async def load(self, config: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Load the latest checkpoint."""
        if self._saver is None:
            return None
        try:
            return self._saver.get(config or {})
        except Exception as exc:
            raise CheckpointError(f"Failed to load checkpoint: {exc}") from exc

    async def replay_from(self, from_offset: int = 0) -> list[EventEnvelope]:
        """Replay checkpoint events from the event store."""
        return await self._event_store.read(
            from_offset=from_offset,
            event_type="kernel.checkpoint.created",
        )
