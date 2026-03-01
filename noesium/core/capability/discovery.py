"""Capability discovery service (RFC-1001 Section 10)."""

from __future__ import annotations

from typing import Any

from noesium.core.projection.base import ProjectionEngine

from .models import DeterminismClass


class DiscoveryService:
    """Query the capability projection for matching capabilities."""

    def __init__(self, projection_engine: ProjectionEngine) -> None:
        self._engine = projection_engine

    async def _state(self) -> dict[str, Any]:
        return await self._engine.get_state("capability")

    async def find(
        self,
        capability_id: str,
        version_range: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find capabilities by id and optional version prefix."""
        state = await self._state()
        caps = state.get("capabilities", {})
        deprecated = state.get("deprecated", set())
        results = []
        for key, entry in caps.items():
            if key in deprecated:
                continue
            if entry.get("capability_id") != capability_id:
                continue
            if version_range and not entry.get("version", "").startswith(version_range):
                continue
            results.append(entry)
        return results

    async def find_by_tag(self, tag: str) -> list[dict[str, Any]]:
        """Find capabilities containing a specific tag."""
        state = await self._state()
        caps = state.get("capabilities", {})
        deprecated = state.get("deprecated", set())
        return [entry for key, entry in caps.items() if key not in deprecated and tag in entry.get("tags", [])]

    async def find_by_determinism(self, cls: DeterminismClass) -> list[dict[str, Any]]:
        """Find capabilities matching a determinism class."""
        state = await self._state()
        caps = state.get("capabilities", {})
        deprecated = state.get("deprecated", set())
        return [entry for key, entry in caps.items() if key not in deprecated and entry.get("determinism") == cls.value]
