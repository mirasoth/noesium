"""Tests for capability models (RFC-0005, RFC-1004)."""

from noesium.core.capability.models import (
    STATEFUL_TYPES,
    CapabilityDescriptor,
    CapabilityQuery,
    CapabilityType,
    DeterminismClass,
    LatencyClass,
    SideEffectClass,
)


class TestEnums:
    def test_capability_type_values(self):
        assert CapabilityType.TOOL.value == "tool"
        assert CapabilityType.MCP_TOOL.value == "mcp_tool"
        assert CapabilityType.SKILL.value == "skill"
        assert CapabilityType.AGENT.value == "agent"
        assert CapabilityType.CLI_AGENT.value == "cli_agent"

    def test_determinism_values(self):
        assert DeterminismClass.DETERMINISTIC.value == "deterministic"
        assert DeterminismClass.STOCHASTIC.value == "stochastic"
        assert DeterminismClass.EXTERNAL.value == "external"

    def test_side_effect_values(self):
        assert SideEffectClass.PURE.value == "pure"
        assert SideEffectClass.IDEMPOTENT.value == "idempotent"
        assert SideEffectClass.EFFECTFUL.value == "effectful"

    def test_latency_values(self):
        assert LatencyClass.REALTIME.value == "realtime"
        assert LatencyClass.FAST.value == "fast"
        assert LatencyClass.BATCH.value == "batch"

    def test_stateful_types(self):
        assert CapabilityType.AGENT in STATEFUL_TYPES
        assert CapabilityType.CLI_AGENT in STATEFUL_TYPES
        assert CapabilityType.TOOL not in STATEFUL_TYPES
        assert CapabilityType.MCP_TOOL not in STATEFUL_TYPES
        assert CapabilityType.SKILL not in STATEFUL_TYPES


class TestCapabilityDescriptor:
    def test_creation_tool(self):
        d = CapabilityDescriptor(
            capability_id="run_bash",
            capability_type=CapabilityType.TOOL,
        )
        assert d.capability_id == "run_bash"
        assert d.version == "1.0.0"
        assert d.capability_type == CapabilityType.TOOL
        assert d.stateful is False
        assert d.determinism == DeterminismClass.STOCHASTIC
        assert d.side_effects == SideEffectClass.PURE
        assert d.latency == LatencyClass.FAST

    def test_creation_agent_is_stateful(self):
        d = CapabilityDescriptor(
            capability_id="agent:helper",
            capability_type=CapabilityType.AGENT,
        )
        assert d.stateful is True

    def test_creation_cli_agent_is_stateful(self):
        d = CapabilityDescriptor(
            capability_id="cli_agent:claude",
            capability_type=CapabilityType.CLI_AGENT,
        )
        assert d.stateful is True

    def test_creation_full(self):
        d = CapabilityDescriptor(
            capability_id="compute",
            version="2.0.0",
            capability_type=CapabilityType.SKILL,
            description="Heavy computation",
            determinism=DeterminismClass.DETERMINISTIC,
            side_effects=SideEffectClass.IDEMPOTENT,
            latency=LatencyClass.BATCH,
            tags=["math", "science"],
        )
        assert d.tags == ["math", "science"]
        assert d.latency == LatencyClass.BATCH
        assert d.stateful is False

    def test_serialization_roundtrip(self):
        d = CapabilityDescriptor(
            capability_id="x",
            capability_type=CapabilityType.TOOL,
            tags=["t1"],
        )
        data = d.model_dump_json()
        restored = CapabilityDescriptor.model_validate_json(data)
        assert restored.capability_id == "x"
        assert restored.tags == ["t1"]
        assert restored.capability_type == CapabilityType.TOOL


class TestCapabilityQuery:
    def test_defaults(self):
        q = CapabilityQuery()
        assert q.capability_id is None
        assert q.healthy_only is True

    def test_with_filters(self):
        q = CapabilityQuery(
            capability_type=CapabilityType.AGENT,
            tag="search",
            healthy_only=False,
        )
        assert q.capability_type == CapabilityType.AGENT
        assert q.tag == "search"
        assert q.healthy_only is False
