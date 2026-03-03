"""Capability data models, provider protocol, and classification enums (RFC-0005)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class CapabilityType(str, Enum):
    TOOL = "tool"
    MCP_TOOL = "mcp_tool"
    SKILL = "skill"
    AGENT = "agent"
    CLI_AGENT = "cli_agent"


class DeterminismClass(str, Enum):
    DETERMINISTIC = "deterministic"
    STOCHASTIC = "stochastic"
    EXTERNAL = "external"


class SideEffectClass(str, Enum):
    PURE = "pure"
    IDEMPOTENT = "idempotent"
    EFFECTFUL = "effectful"


class LatencyClass(str, Enum):
    REALTIME = "realtime"
    FAST = "fast"
    BATCH = "batch"


STATEFUL_TYPES = frozenset({CapabilityType.AGENT, CapabilityType.CLI_AGENT})


class CapabilityDescriptor(BaseModel):
    """Typed contract describing what a capability can do."""

    capability_id: str
    version: str = "1.0.0"
    capability_type: CapabilityType
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    determinism: DeterminismClass = DeterminismClass.STOCHASTIC
    side_effects: SideEffectClass = SideEffectClass.PURE
    latency: LatencyClass = LatencyClass.FAST
    tags: list[str] = Field(default_factory=list)

    @property
    def stateful(self) -> bool:
        return self.capability_type in STATEFUL_TYPES


@runtime_checkable
class CapabilityProvider(Protocol):
    """Anything that provides a capability: tool, MCP tool, skill, or agent."""

    @property
    def descriptor(self) -> CapabilityDescriptor: ...

    async def invoke(self, **kwargs: Any) -> Any: ...

    async def health(self) -> bool: ...


class CapabilityQuery(BaseModel):
    """Structured query for capability discovery."""

    capability_id: str | None = None
    version: str | None = None
    capability_type: CapabilityType | None = None
    tag: str | None = None
    determinism: DeterminismClass | None = None
    healthy_only: bool = True
