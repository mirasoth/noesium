"""Unified capability registry with hybrid event sourcing (RFC-0005).

Provider-first design: the in-memory provider dict is the source of truth for
fast reads.  An append-only changelog is maintained for audit.  When an
``EventStore`` is supplied, changelog entries are flushed asynchronously for
persistence and cross-process replay.  ``rebuild_from_events()`` reconstructs
the provider dict from a persisted event stream on cold start.

Health model:
- Stateless providers (TOOL, MCP_TOOL, SKILL): ``health()`` always returns True.
- Stateful providers (AGENT, CLI_AGENT): monitored by a background heartbeat
  task that polls ``provider.health()`` at a configurable interval.  Cached
  health status is used by ``resolve()`` to skip unhealthy providers.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from noesium.core.event.envelope import AgentRef, TraceContext
from noesium.core.event.store import EventStore
from noesium.core.event.types import CapabilityRegistered
from noesium.core.exceptions import CapabilityNotFoundError

from .models import (
    CapabilityDescriptor,
    CapabilityProvider,
    CapabilityQuery,
    CapabilityType,
    DeterminismClass,
)

logger = logging.getLogger(__name__)

RegistryListener = Callable[["RegistryEvent"], Any]


@dataclass
class RegistryEvent:
    """Lightweight audit record emitted on every registry mutation."""

    action: str  # "registered" | "unregistered" | "health_changed"
    capability_id: str
    version: str
    capability_type: str
    timestamp: float = field(default_factory=time.time)
    detail: dict[str, Any] = field(default_factory=dict)


class CapabilityRegistry:
    """Unified registry for all capability providers.

    Replaces the former ``ToolRegistry``, ``DiscoveryService``, and
    ``DeterministicResolver`` with a single entry-point.
    """

    def __init__(
        self,
        event_store: EventStore | None = None,
        producer: AgentRef | None = None,
        health_interval: float = 10.0,
    ) -> None:
        self._providers: dict[str, list[CapabilityProvider]] = {}
        self._by_name: dict[str, CapabilityProvider] = {}
        self._changelog: list[RegistryEvent] = []
        self._listeners: list[RegistryListener] = []

        self._event_store = event_store
        self._producer = producer or AgentRef(agent_id="registry", agent_type="system")
        self._trace = TraceContext()

        self._health_cache: dict[str, bool] = {}
        self._health_interval = health_interval
        self._health_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, provider: CapabilityProvider) -> None:
        """Add a provider to the registry."""
        d = provider.descriptor
        key = d.capability_id
        self._providers.setdefault(key, []).append(provider)
        self._by_name[key] = provider

        if d.stateful:
            self._health_cache[key] = True

        evt = RegistryEvent(
            action="registered",
            capability_id=d.capability_id,
            version=d.version,
            capability_type=d.capability_type.value,
            detail={"description": d.description, "tags": d.tags},
        )
        self._changelog.append(evt)
        self._notify(evt)
        self._flush_event_async(d)

    def register_many(self, providers: list[CapabilityProvider]) -> None:
        for p in providers:
            self.register(p)

    def unregister(self, capability_id: str, version: str | None = None) -> None:
        """Remove providers matching ``capability_id`` (and optionally ``version``)."""
        providers = self._providers.get(capability_id, [])
        if version:
            kept = [p for p in providers if p.descriptor.version != version]
            removed = [p for p in providers if p.descriptor.version == version]
        else:
            kept = []
            removed = providers

        if not removed:
            return

        if kept:
            self._providers[capability_id] = kept
            self._by_name[capability_id] = kept[-1]
        else:
            self._providers.pop(capability_id, None)
            self._by_name.pop(capability_id, None)

        self._health_cache.pop(capability_id, None)

        for p in removed:
            d = p.descriptor
            evt = RegistryEvent(
                action="unregistered",
                capability_id=d.capability_id,
                version=d.version,
                capability_type=d.capability_type.value,
            )
            self._changelog.append(evt)
            self._notify(evt)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def find(
        self,
        capability_id: str,
        version: str | None = None,
    ) -> list[CapabilityProvider]:
        """Find providers by capability_id with optional version prefix filter."""
        candidates = self._providers.get(capability_id, [])
        if version:
            candidates = [
                p for p in candidates if p.descriptor.version.startswith(version)
            ]
        return candidates

    def find_by_type(self, cap_type: CapabilityType) -> list[CapabilityProvider]:
        result: list[CapabilityProvider] = []
        for providers in self._providers.values():
            for p in providers:
                if p.descriptor.capability_type == cap_type:
                    result.append(p)
        return result

    def find_by_tag(self, tag: str) -> list[CapabilityProvider]:
        result: list[CapabilityProvider] = []
        for providers in self._providers.values():
            for p in providers:
                if tag in p.descriptor.tags:
                    result.append(p)
        return result

    def find_by_determinism(self, cls: DeterminismClass) -> list[CapabilityProvider]:
        result: list[CapabilityProvider] = []
        for providers in self._providers.values():
            for p in providers:
                if p.descriptor.determinism == cls:
                    result.append(p)
        return result

    def query(self, q: CapabilityQuery) -> list[CapabilityProvider]:
        """Structured query across all registered providers."""
        result: list[CapabilityProvider] = []
        for providers in self._providers.values():
            for p in providers:
                d = p.descriptor
                if q.capability_id and d.capability_id != q.capability_id:
                    continue
                if q.version and not d.version.startswith(q.version):
                    continue
                if q.capability_type and d.capability_type != q.capability_type:
                    continue
                if q.tag and q.tag not in d.tags:
                    continue
                if q.determinism and d.determinism != q.determinism:
                    continue
                if q.healthy_only and d.stateful:
                    if not self._health_cache.get(d.capability_id, True):
                        continue
                result.append(p)
        return result

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    async def resolve(
        self,
        capability_id: str,
        version: str | None = None,
    ) -> CapabilityProvider:
        """Deterministic resolution: first healthy match by registration order.

        For stateless providers health is always True (no I/O).
        For stateful providers the cached health status is used (updated by
        the background heartbeat task).
        """
        candidates = self.find(capability_id, version)
        for p in candidates:
            if p.descriptor.stateful:
                if not self._health_cache.get(p.descriptor.capability_id, True):
                    continue
            return p
        raise CapabilityNotFoundError(
            f"No healthy capability found: {capability_id}"
            + (f" version={version}" if version else "")
        )

    def get_by_name(self, name: str) -> CapabilityProvider:
        """Fast O(1) lookup by capability_id (last registered wins)."""
        if name not in self._by_name:
            raise CapabilityNotFoundError(f"Capability '{name}' not registered")
        return self._by_name[name]

    # ------------------------------------------------------------------
    # Listing & introspection
    # ------------------------------------------------------------------

    def list_providers(
        self,
        cap_type: CapabilityType | None = None,
    ) -> list[CapabilityProvider]:
        """Return all registered providers, optionally filtered by type."""
        result: list[CapabilityProvider] = []
        for providers in self._providers.values():
            for p in providers:
                if cap_type and p.descriptor.capability_type != cap_type:
                    continue
                result.append(p)
        return result

    def list_descriptors(self) -> list[CapabilityDescriptor]:
        return [p.descriptor for p in self.list_providers()]

    @property
    def changelog(self) -> list[RegistryEvent]:
        return list(self._changelog)

    # ------------------------------------------------------------------
    # Observer / listener
    # ------------------------------------------------------------------

    def add_listener(self, listener: RegistryListener) -> None:
        self._listeners.append(listener)

    def _notify(self, evt: RegistryEvent) -> None:
        for listener in self._listeners:
            try:
                listener(evt)
            except Exception:
                logger.debug("Registry listener error", exc_info=True)

    # ------------------------------------------------------------------
    # Health monitoring (background heartbeat for stateful providers)
    # ------------------------------------------------------------------

    def start_health_monitor(self) -> None:
        """Start background task that polls health on stateful providers."""
        if self._health_task is not None:
            return
        self._health_task = asyncio.ensure_future(self._health_loop())

    async def stop_health_monitor(self) -> None:
        if self._health_task is not None:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None

    async def _health_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._health_interval)
                await self._poll_stateful_health()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.debug("Health monitor error", exc_info=True)

    async def _poll_stateful_health(self) -> None:
        for providers in self._providers.values():
            for p in providers:
                if not p.descriptor.stateful:
                    continue
                cap_id = p.descriptor.capability_id
                try:
                    alive = await p.health()
                except Exception:
                    alive = False
                prev = self._health_cache.get(cap_id, True)
                self._health_cache[cap_id] = alive
                if prev != alive:
                    evt = RegistryEvent(
                        action="health_changed",
                        capability_id=cap_id,
                        version=p.descriptor.version,
                        capability_type=p.descriptor.capability_type.value,
                        detail={"healthy": alive},
                    )
                    self._changelog.append(evt)
                    self._notify(evt)

    def get_health(self, capability_id: str) -> bool | None:
        """Return cached health for a capability, or None if not tracked."""
        return self._health_cache.get(capability_id)

    # ------------------------------------------------------------------
    # Hybrid event sourcing
    # ------------------------------------------------------------------

    def _flush_event_async(self, descriptor: CapabilityDescriptor) -> None:
        """Fire-and-forget: emit a CapabilityRegistered event to EventStore."""
        if self._event_store is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._flush_event(descriptor))

    async def _flush_event(self, descriptor: CapabilityDescriptor) -> None:
        if self._event_store is None:
            return
        try:
            event = CapabilityRegistered(
                capability_id=descriptor.capability_id,
                version=descriptor.version,
                agent_id=self._producer.agent_id,
            )
            envelope = event.to_envelope(producer=self._producer, trace=self._trace)
            envelope.payload.update(
                {
                    "capability_type": descriptor.capability_type.value,
                    "description": descriptor.description,
                    "tags": descriptor.tags,
                    "determinism": descriptor.determinism.value,
                    "side_effects": descriptor.side_effects.value,
                    "latency": descriptor.latency.value,
                    "input_schema": descriptor.input_schema,
                    "output_schema": descriptor.output_schema,
                }
            )
            await self._event_store.append(envelope)
        except Exception:
            logger.debug(
                "Failed to flush capability event to EventStore", exc_info=True
            )

    async def rebuild_from_events(self, event_store: EventStore) -> int:
        """Reconstruct changelog from a persisted event stream (cold-start).

        Returns the number of events replayed.  Does NOT reconstruct live
        providers -- those must be re-registered by the agent on startup.
        The changelog is useful for audit replay.
        """
        events = await event_store.read()
        count = 0
        for env in events:
            if env.event_type == "capability.registered":
                p = env.payload
                self._changelog.append(
                    RegistryEvent(
                        action="registered",
                        capability_id=p.get("capability_id", ""),
                        version=p.get("version", "1.0.0"),
                        capability_type=p.get("capability_type", "tool"),
                        timestamp=(
                            env.timestamp.timestamp() if env.timestamp else time.time()
                        ),
                        detail={
                            k: v
                            for k, v in p.items()
                            if k not in ("capability_id", "version")
                        },
                    )
                )
                count += 1
            elif env.event_type == "capability.deprecated":
                p = env.payload
                self._changelog.append(
                    RegistryEvent(
                        action="unregistered",
                        capability_id=p.get("capability_id", ""),
                        version=p.get("version", "1.0.0"),
                        capability_type="unknown",
                        timestamp=(
                            env.timestamp.timestamp() if env.timestamp else time.time()
                        ),
                    )
                )
                count += 1
        return count
