"""Semantic projection stub for future vector indexing (RFC-1001 Section 8.3)."""

from __future__ import annotations

from typing import Any

from noesium.core.event.envelope import EventEnvelope

from .base import BaseProjection

SemanticState = dict[str, Any]


class SemanticProjection(BaseProjection[SemanticState]):
    """Builds an index list from events. Real vector indexing is deferred."""

    def initial_state(self) -> SemanticState:
        return {"index_entries": [], "count": 0}

    def apply(self, state: SemanticState, event: EventEnvelope) -> SemanticState:
        if event.event_type == "memory.written":
            state["index_entries"].append(
                {
                    "key": event.payload.get("key", ""),
                    "value": event.payload.get("value"),
                    "event_id": event.event_id,
                }
            )
            state["count"] += 1
        return state
