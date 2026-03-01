"""Tests for capability models."""

from noesium.core.capability.models import (
    Capability,
    DeterminismClass,
    LatencyClass,
    SideEffectClass,
)


class TestEnums:
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


class TestCapability:
    def test_creation_defaults(self):
        cap = Capability(capability_id="search", agent_id="a1")
        assert cap.capability_id == "search"
        assert cap.version == "1.0.0"
        assert cap.determinism == DeterminismClass.STOCHASTIC
        assert cap.side_effects == SideEffectClass.PURE
        assert cap.latency == LatencyClass.FAST
        assert cap.deprecated is False
        assert cap.id  # auto-generated

    def test_creation_full(self):
        cap = Capability(
            capability_id="compute",
            agent_id="a2",
            version="2.0.0",
            description="Heavy computation",
            determinism=DeterminismClass.DETERMINISTIC,
            side_effects=SideEffectClass.IDEMPOTENT,
            latency=LatencyClass.BATCH,
            tags=["math", "science"],
            roles=["worker"],
            scopes=["internal"],
        )
        assert cap.tags == ["math", "science"]
        assert cap.latency == LatencyClass.BATCH

    def test_serialization_roundtrip(self):
        cap = Capability(capability_id="x", agent_id="a1", tags=["t1"])
        data = cap.model_dump_json()
        restored = Capability.model_validate_json(data)
        assert restored.capability_id == "x"
        assert restored.tags == ["t1"]
