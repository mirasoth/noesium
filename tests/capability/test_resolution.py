"""Tests for DiscoveryService and DeterministicResolver."""

import pytest

from noesium.core.capability.discovery import DiscoveryService
from noesium.core.capability.models import Capability, DeterminismClass
from noesium.core.capability.registry import CapabilityRegistry
from noesium.core.capability.resolution import DeterministicResolver
from noesium.core.event.store import InMemoryEventStore
from noesium.core.exceptions import CapabilityNotFoundError
from noesium.core.projection.base import ProjectionEngine


@pytest.fixture()
def store():
    return InMemoryEventStore()


@pytest.fixture()
def engine(store):
    return ProjectionEngine(event_store=store)


@pytest.fixture()
def registry(store, engine):
    return CapabilityRegistry(event_store=store, projection_engine=engine)


@pytest.fixture()
def discovery(engine):
    return DiscoveryService(projection_engine=engine)


@pytest.fixture()
def resolver(discovery):
    return DeterministicResolver(discovery=discovery)


class TestDiscoveryService:
    @pytest.mark.asyncio
    async def test_find_by_id(self, registry, discovery):
        await registry.register(Capability(capability_id="search", agent_id="a1"))
        results = await discovery.find("search")
        assert len(results) == 1
        assert results[0]["capability_id"] == "search"

    @pytest.mark.asyncio
    async def test_find_excludes_deprecated(self, registry, discovery):
        await registry.register(Capability(capability_id="old", agent_id="a1"))
        await registry.deprecate("old")
        results = await discovery.find("old")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_find_by_tag(self, registry, discovery):
        await registry.register(Capability(capability_id="c1", agent_id="a1", tags=["web"]))
        await registry.register(Capability(capability_id="c2", agent_id="a2", tags=["math"]))
        results = await discovery.find_by_tag("web")
        assert len(results) == 1
        assert results[0]["capability_id"] == "c1"

    @pytest.mark.asyncio
    async def test_find_by_determinism(self, registry, discovery):
        await registry.register(
            Capability(capability_id="pure", agent_id="a1", determinism=DeterminismClass.DETERMINISTIC)
        )
        await registry.register(Capability(capability_id="llm", agent_id="a2", determinism=DeterminismClass.STOCHASTIC))
        results = await discovery.find_by_determinism(DeterminismClass.DETERMINISTIC)
        assert len(results) == 1


class TestDeterministicResolver:
    @pytest.mark.asyncio
    async def test_resolve_returns_first_match(self, registry, resolver):
        await registry.register(Capability(capability_id="search", agent_id="a1"))
        await registry.register(Capability(capability_id="search", agent_id="a2", version="2.0.0"))
        result = await resolver.resolve("search")
        assert result["agent_id"] == "a1"

    @pytest.mark.asyncio
    async def test_resolve_with_version_filter(self, registry, resolver):
        await registry.register(Capability(capability_id="x", agent_id="a1", version="1.0.0"))
        await registry.register(Capability(capability_id="x", agent_id="a2", version="2.0.0"))
        result = await resolver.resolve("x", version_range="2")
        assert result["version"] == "2.0.0"

    @pytest.mark.asyncio
    async def test_resolve_not_found(self, registry, resolver):
        with pytest.raises(CapabilityNotFoundError):
            await resolver.resolve("nonexistent")

    @pytest.mark.asyncio
    async def test_stable_ordering(self, registry, resolver):
        """Same query always returns the same result."""
        for i in range(3):
            await registry.register(Capability(capability_id="s", agent_id=f"a{i}", version=f"{i}.0.0"))
        r1 = await resolver.resolve("s")
        r2 = await resolver.resolve("s")
        assert r1["agent_id"] == r2["agent_id"]
