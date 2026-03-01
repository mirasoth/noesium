"""Capability registry backed by projections (RFC-1001 Section 10)."""

from __future__ import annotations

from typing import Any

from noesium.core.event.envelope import AgentRef, EventEnvelope, TraceContext
from noesium.core.event.store import EventStore
from noesium.core.event.types import CapabilityRegistered
from noesium.core.projection.base import BaseProjection, ProjectionEngine

from .models import Capability


class CapabilityProjection(BaseProjection[dict[str, Any]]):
    """Derives the current set of capabilities from registration events."""

    def initial_state(self) -> dict[str, Any]:
        return {"capabilities": {}, "deprecated": set()}

    def apply(self, state: dict[str, Any], event: EventEnvelope) -> dict[str, Any]:
        et = event.event_type
        p = event.payload

        if et == "capability.registered":
            cap_id = p.get("capability_id", "")
            version = p.get("version", "1.0.0")
            key = f"{cap_id}@{version}"
            state["capabilities"][key] = {
                "capability_id": cap_id,
                "version": version,
                "agent_id": p.get("agent_id", ""),
                "event_id": event.event_id,
                **{k: v for k, v in p.items() if k not in ("capability_id", "version", "agent_id")},
            }

        elif et == "capability.deprecated":
            cap_id = p.get("capability_id", "")
            version = p.get("version", "1.0.0")
            key = f"{cap_id}@{version}"
            state["deprecated"].add(key)

        return state


class CapabilityRegistry:
    """Register and deprecate capabilities via event emission."""

    def __init__(
        self,
        event_store: EventStore,
        projection_engine: ProjectionEngine,
        producer: AgentRef | None = None,
    ) -> None:
        self._store = event_store
        self._engine = projection_engine
        self._producer = producer or AgentRef(agent_id="registry", agent_type="system")
        self._trace = TraceContext()

        self._projection = CapabilityProjection()
        self._engine.register("capability", self._projection)

    async def register(self, capability: Capability) -> None:
        """Register a capability by emitting a ``CapabilityRegistered`` event."""
        event = CapabilityRegistered(
            capability_id=capability.capability_id,
            version=capability.version,
            agent_id=capability.agent_id,
        )
        envelope = event.to_envelope(
            producer=self._producer,
            trace=self._trace,
        )
        envelope.payload.update(capability.model_dump(exclude={"id"}))
        await self._store.append(envelope)
        await self._engine.apply_event(envelope)

    async def deprecate(self, capability_id: str, version: str = "1.0.0") -> None:
        """Mark a capability as deprecated."""
        envelope = EventEnvelope(
            event_type="capability.deprecated",
            producer=self._producer,
            trace=self._trace,
            payload={"capability_id": capability_id, "version": version},
        )
        await self._store.append(envelope)
        await self._engine.apply_event(envelope)

    async def get_state(self) -> dict[str, Any]:
        """Return the current capability projection state."""
        return await self._engine.get_state("capability")
