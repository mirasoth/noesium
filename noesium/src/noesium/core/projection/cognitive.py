"""Cognitive projection tracking memory writes and reasoning (RFC-1001 Section 8.2)."""

from __future__ import annotations

from typing import Any

from noesium.core.event.envelope import EventEnvelope

from .base import BaseProjection

CognitiveState = dict[str, Any]


class CognitiveProjection(BaseProjection[CognitiveState]):
    """Accumulates memory writes and reasoning-related events."""

    def initial_state(self) -> CognitiveState:
        return {
            "memory_entries": {},
            "reasoning_traces": [],
            "write_count": 0,
        }

    def apply(self, state: CognitiveState, event: EventEnvelope) -> CognitiveState:
        et = event.event_type
        p = event.payload

        if et == "memory.written":
            key = p.get("key", "")
            state["memory_entries"][key] = {
                "value": p.get("value"),
                "value_type": p.get("value_type", "unknown"),
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
            }
            state["write_count"] += 1

        elif et == "system.error.occurred":
            state["reasoning_traces"].append(
                {
                    "type": "error",
                    "error_type": p.get("error_type", ""),
                    "message": p.get("message", ""),
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                }
            )

        return state
