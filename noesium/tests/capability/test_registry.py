"""Tests for unified CapabilityRegistry (RFC-1003, RFC-2003)."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from noesium.core.capability.models import (
    CapabilityDescriptor,
    CapabilityQuery,
    CapabilityType,
    DeterminismClass,
)
from noesium.core.capability.registry import CapabilityRegistry, RegistryEvent
from noesium.core.exceptions import CapabilityNotFoundError


def _make_provider(
    capability_id: str = "test_tool",
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


class TestRegistration:
    def test_register_and_find(self):
        reg = CapabilityRegistry()
        p = _make_provider("search")
        reg.register(p)

        found = reg.find("search")
        assert len(found) == 1
        assert found[0] is p

    def test_register_many(self):
        reg = CapabilityRegistry()
        p1 = _make_provider("a")
        p2 = _make_provider("b")
        reg.register_many([p1, p2])
        assert len(reg.list_providers()) == 2

    def test_get_by_name(self):
        reg = CapabilityRegistry()
        p = _make_provider("my_tool")
        reg.register(p)
        assert reg.get_by_name("my_tool") is p

    def test_get_by_name_not_found(self):
        reg = CapabilityRegistry()
        with pytest.raises(CapabilityNotFoundError):
            reg.get_by_name("nonexistent")

    def test_unregister(self):
        reg = CapabilityRegistry()
        p = _make_provider("old")
        reg.register(p)
        reg.unregister("old")
        assert reg.find("old") == []

    def test_unregister_with_version(self):
        reg = CapabilityRegistry()
        p1 = _make_provider("x", version="1.0.0")
        p2 = _make_provider("x", version="2.0.0")
        reg.register(p1)
        reg.register(p2)
        reg.unregister("x", version="1.0.0")
        found = reg.find("x")
        assert len(found) == 1
        assert found[0].descriptor.version == "2.0.0"

    def test_changelog_on_register(self):
        reg = CapabilityRegistry()
        reg.register(_make_provider("a"))
        assert len(reg.changelog) == 1
        assert reg.changelog[0].action == "registered"
        assert reg.changelog[0].capability_id == "a"

    def test_changelog_on_unregister(self):
        reg = CapabilityRegistry()
        reg.register(_make_provider("b"))
        reg.unregister("b")
        assert len(reg.changelog) == 2
        assert reg.changelog[1].action == "unregistered"


class TestDiscovery:
    def test_find_by_type(self):
        reg = CapabilityRegistry()
        reg.register(_make_provider("t1", cap_type=CapabilityType.TOOL))
        reg.register(_make_provider("a1", cap_type=CapabilityType.AGENT))
        reg.register(_make_provider("m1", cap_type=CapabilityType.MCP_TOOL))

        tools = reg.find_by_type(CapabilityType.TOOL)
        assert len(tools) == 1
        agents = reg.find_by_type(CapabilityType.AGENT)
        assert len(agents) == 1

    def test_find_by_tag(self):
        reg = CapabilityRegistry()
        reg.register(_make_provider("c1", tags=["web", "search"]))
        reg.register(_make_provider("c2", tags=["math"]))

        results = reg.find_by_tag("web")
        assert len(results) == 1
        assert results[0].descriptor.capability_id == "c1"

    def test_find_by_determinism(self):
        reg = CapabilityRegistry()
        reg.register(_make_provider("det", determinism=DeterminismClass.DETERMINISTIC))
        reg.register(_make_provider("sto", determinism=DeterminismClass.STOCHASTIC))

        results = reg.find_by_determinism(DeterminismClass.DETERMINISTIC)
        assert len(results) == 1

    def test_find_with_version_filter(self):
        reg = CapabilityRegistry()
        reg.register(_make_provider("x", version="1.0.0"))
        reg.register(_make_provider("x", version="2.0.0"))

        results = reg.find("x", version="2")
        assert len(results) == 1
        assert results[0].descriptor.version == "2.0.0"

    def test_query_combined(self):
        reg = CapabilityRegistry()
        reg.register(_make_provider("a", cap_type=CapabilityType.TOOL, tags=["web"]))
        reg.register(_make_provider("b", cap_type=CapabilityType.AGENT, tags=["web"]))
        reg.register(_make_provider("c", cap_type=CapabilityType.TOOL, tags=["math"]))

        q = CapabilityQuery(capability_type=CapabilityType.TOOL, tag="web")
        results = reg.query(q)
        assert len(results) == 1
        assert results[0].descriptor.capability_id == "a"

    def test_list_descriptors(self):
        reg = CapabilityRegistry()
        reg.register(_make_provider("x"))
        reg.register(_make_provider("y"))
        descs = reg.list_descriptors()
        assert len(descs) == 2
        assert all(isinstance(d, CapabilityDescriptor) for d in descs)


class TestResolution:
    @pytest.mark.asyncio
    async def test_resolve_returns_first_match(self):
        reg = CapabilityRegistry()
        p1 = _make_provider("search", version="1.0.0")
        p2 = _make_provider("search", version="2.0.0")
        reg.register(p1)
        reg.register(p2)

        resolved = await reg.resolve("search")
        assert resolved is p1

    @pytest.mark.asyncio
    async def test_resolve_with_version(self):
        reg = CapabilityRegistry()
        reg.register(_make_provider("x", version="1.0.0"))
        reg.register(_make_provider("x", version="2.0.0"))

        resolved = await reg.resolve("x", version="2")
        assert resolved.descriptor.version == "2.0.0"

    @pytest.mark.asyncio
    async def test_resolve_not_found(self):
        reg = CapabilityRegistry()
        with pytest.raises(CapabilityNotFoundError):
            await reg.resolve("nonexistent")

    @pytest.mark.asyncio
    async def test_resolve_stable_ordering(self):
        reg = CapabilityRegistry()
        for i in range(3):
            reg.register(_make_provider("s", version=f"{i}.0.0"))

        r1 = await reg.resolve("s")
        r2 = await reg.resolve("s")
        assert r1.descriptor.version == r2.descriptor.version

    @pytest.mark.asyncio
    async def test_resolve_skips_unhealthy_stateful(self):
        """Unhealthy stateful providers are skipped; stateless ones unaffected."""
        reg = CapabilityRegistry()
        agent_p = _make_provider("agent:a", cap_type=CapabilityType.AGENT)
        tool_p = _make_provider("my_tool", cap_type=CapabilityType.TOOL)
        reg.register(agent_p)
        reg.register(tool_p)
        reg._health_cache["agent:a"] = False

        with pytest.raises(CapabilityNotFoundError):
            await reg.resolve("agent:a")

        resolved_tool = await reg.resolve("my_tool")
        assert resolved_tool is tool_p


class TestHealthMonitor:
    @pytest.mark.asyncio
    async def test_poll_stateful_health(self):
        reg = CapabilityRegistry()
        p = _make_provider("agent:x", cap_type=CapabilityType.AGENT, healthy=False)
        reg.register(p)
        reg._health_cache["agent:x"] = True

        await reg._poll_stateful_health()

        assert reg._health_cache["agent:x"] is False
        assert any(e.action == "health_changed" for e in reg.changelog)

    def test_get_health(self):
        reg = CapabilityRegistry()
        assert reg.get_health("unknown") is None

        reg._health_cache["test"] = True
        assert reg.get_health("test") is True


class TestListener:
    def test_listener_called_on_register(self):
        reg = CapabilityRegistry()
        events: list[RegistryEvent] = []
        reg.add_listener(events.append)

        reg.register(_make_provider("t"))
        assert len(events) == 1
        assert events[0].action == "registered"

    def test_listener_called_on_unregister(self):
        reg = CapabilityRegistry()
        events: list[RegistryEvent] = []
        reg.add_listener(events.append)

        reg.register(_make_provider("t"))
        reg.unregister("t")
        assert len(events) == 2
        assert events[1].action == "unregistered"
