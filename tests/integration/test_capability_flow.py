"""Integration test: capability registration -> discovery -> deterministic resolution."""

import pytest

from noesium.core.capability.discovery import DiscoveryService
from noesium.core.capability.models import Capability, DeterminismClass
from noesium.core.capability.registry import CapabilityRegistry
from noesium.core.capability.resolution import DeterministicResolver
from noesium.core.event.store import InMemoryEventStore
from noesium.core.exceptions import CapabilityNotFoundError
from noesium.core.projection.base import ProjectionEngine


@pytest.mark.integration
class TestCapabilityFlow:
    @pytest.mark.asyncio
    async def test_two_agents_register_discover_resolve(self):
        store = InMemoryEventStore()
        engine = ProjectionEngine(event_store=store)
        registry = CapabilityRegistry(event_store=store, projection_engine=engine)
        discovery = DiscoveryService(projection_engine=engine)
        resolver = DeterministicResolver(discovery=discovery)

        await registry.register(
            Capability(
                capability_id="web_search",
                agent_id="search-agent-1",
                version="1.0.0",
                tags=["search", "web"],
                determinism=DeterminismClass.EXTERNAL,
            )
        )
        await registry.register(
            Capability(
                capability_id="web_search",
                agent_id="search-agent-2",
                version="2.0.0",
                tags=["search", "web"],
                determinism=DeterminismClass.EXTERNAL,
            )
        )
        await registry.register(
            Capability(
                capability_id="math_compute",
                agent_id="math-agent",
                version="1.0.0",
                tags=["math"],
                determinism=DeterminismClass.DETERMINISTIC,
            )
        )

        all_search = await discovery.find("web_search")
        assert len(all_search) == 2

        web_tag = await discovery.find_by_tag("web")
        assert len(web_tag) == 2

        deterministic = await discovery.find_by_determinism(DeterminismClass.DETERMINISTIC)
        assert len(deterministic) == 1
        assert deterministic[0]["capability_id"] == "math_compute"

        resolved = await resolver.resolve("web_search")
        assert resolved["agent_id"] == "search-agent-1"

        resolved_v2 = await resolver.resolve("web_search", version_range="2")
        assert resolved_v2["version"] == "2.0.0"

    @pytest.mark.asyncio
    async def test_deprecation_hides_from_discovery(self):
        store = InMemoryEventStore()
        engine = ProjectionEngine(event_store=store)
        registry = CapabilityRegistry(event_store=store, projection_engine=engine)
        discovery = DiscoveryService(projection_engine=engine)
        resolver = DeterministicResolver(discovery=discovery)

        await registry.register(Capability(capability_id="old_api", agent_id="a1"))
        await registry.deprecate("old_api")

        results = await discovery.find("old_api")
        assert len(results) == 0

        with pytest.raises(CapabilityNotFoundError):
            await resolver.resolve("old_api")
