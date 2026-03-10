"""Integration test: capability registration -> discovery -> resolution via unified registry."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from noesium.core.capability.models import (
    CapabilityDescriptor,
    CapabilityQuery,
    CapabilityType,
    DeterminismClass,
)
from noesium.core.capability.registry import CapabilityRegistry
from noesium.core.exceptions import CapabilityNotFoundError


def _make_provider(
    capability_id: str,
    cap_type: CapabilityType = CapabilityType.TOOL,
    version: str = "1.0.0",
    tags: list[str] | None = None,
    determinism: DeterminismClass = DeterminismClass.STOCHASTIC,
    healthy: bool = True,
) -> MagicMock:
    desc = CapabilityDescriptor(
        capability_id=capability_id,
        capability_type=cap_type,
        version=version,
        tags=tags or [],
        determinism=determinism,
    )
    p = MagicMock()
    type(p).descriptor = PropertyMock(return_value=desc)
    p.invoke = AsyncMock(return_value="result")
    p.health = AsyncMock(return_value=healthy)
    return p


@pytest.mark.integration
class TestCapabilityFlow:
    @pytest.mark.asyncio
    async def test_register_discover_resolve(self):
        reg = CapabilityRegistry()

        reg.register(
            _make_provider(
                "web_search",
                version="1.0.0",
                tags=["search", "web"],
                determinism=DeterminismClass.EXTERNAL,
            )
        )
        reg.register(
            _make_provider(
                "web_search",
                version="2.0.0",
                tags=["search", "web"],
                determinism=DeterminismClass.EXTERNAL,
            )
        )
        reg.register(
            _make_provider(
                "math_compute",
                tags=["math"],
                determinism=DeterminismClass.DETERMINISTIC,
            )
        )

        all_search = reg.find("web_search")
        assert len(all_search) == 2

        web_tag = reg.find_by_tag("web")
        assert len(web_tag) == 2

        deterministic = reg.find_by_determinism(DeterminismClass.DETERMINISTIC)
        assert len(deterministic) == 1
        assert deterministic[0].descriptor.capability_id == "math_compute"

        resolved = await reg.resolve("web_search")
        assert resolved.descriptor.version == "1.0.0"

        resolved_v2 = await reg.resolve("web_search", version="2")
        assert resolved_v2.descriptor.version == "2.0.0"

    @pytest.mark.asyncio
    async def test_unregister_hides_from_discovery(self):
        reg = CapabilityRegistry()
        reg.register(_make_provider("old_api"))
        reg.unregister("old_api")

        results = reg.find("old_api")
        assert len(results) == 0

        with pytest.raises(CapabilityNotFoundError):
            await reg.resolve("old_api")

    @pytest.mark.asyncio
    async def test_mixed_types_query(self):
        reg = CapabilityRegistry()
        reg.register(_make_provider("bash", cap_type=CapabilityType.TOOL, tags=["shell"]))
        reg.register(_make_provider("mcp_search", cap_type=CapabilityType.MCP_TOOL, tags=["search"]))
        reg.register(_make_provider("agent:helper", cap_type=CapabilityType.AGENT))
        reg.register(_make_provider("cli_agent:claude", cap_type=CapabilityType.CLI_AGENT))

        tools = reg.find_by_type(CapabilityType.TOOL)
        assert len(tools) == 1
        agents = reg.find_by_type(CapabilityType.AGENT)
        assert len(agents) == 1
        cli = reg.find_by_type(CapabilityType.CLI_AGENT)
        assert len(cli) == 1

        q = CapabilityQuery(tag="shell")
        results = reg.query(q)
        assert len(results) == 1
        assert results[0].descriptor.capability_id == "bash"

    @pytest.mark.asyncio
    async def test_health_aware_resolution(self):
        """Unhealthy stateful providers are excluded from resolution."""
        reg = CapabilityRegistry()
        agent_unhealthy = _make_provider(
            "agent:worker",
            cap_type=CapabilityType.AGENT,
        )
        agent_healthy = _make_provider(
            "agent:backup",
            cap_type=CapabilityType.AGENT,
        )
        reg.register(agent_unhealthy)
        reg.register(agent_healthy)
        reg._health_cache["agent:worker"] = False
        reg._health_cache["agent:backup"] = True

        with pytest.raises(CapabilityNotFoundError):
            await reg.resolve("agent:worker")

        resolved = await reg.resolve("agent:backup")
        assert resolved.descriptor.capability_id == "agent:backup"

    @pytest.mark.asyncio
    async def test_listener_observes_lifecycle(self):
        reg = CapabilityRegistry()
        events = []
        reg.add_listener(events.append)

        reg.register(_make_provider("x"))
        reg.unregister("x")

        assert len(events) == 2
        assert events[0].action == "registered"
        assert events[1].action == "unregistered"
