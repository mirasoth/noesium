"""Deterministic capability resolution (RFC-1001 Section 10)."""

from __future__ import annotations

from typing import Any

from noesium.core.exceptions import CapabilityNotFoundError

from .discovery import DiscoveryService


class DeterministicResolver:
    """Resolves a capability to a single provider deterministically.

    Given multiple matches, returns the first by registration order (stable).
    No randomness is introduced.
    """

    def __init__(self, discovery: DiscoveryService) -> None:
        self._discovery = discovery

    async def resolve(
        self,
        capability_id: str,
        version_range: str | None = None,
    ) -> dict[str, Any]:
        """Return the first matching capability, or raise."""
        matches = await self._discovery.find(capability_id, version_range)
        if not matches:
            raise CapabilityNotFoundError(
                f"No capability found: {capability_id}" + (f" version={version_range}" if version_range else "")
            )
        return matches[0]
