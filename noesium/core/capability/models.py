"""Capability data models and classification enums (RFC-0005, RFC-1001 Section 10)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from uuid_extensions import uuid7str


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


class Capability(BaseModel):
    """Declarative description of a capability offered by an agent."""

    id: str = Field(default_factory=lambda: uuid7str())
    capability_id: str
    version: str = "1.0.0"
    agent_id: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    determinism: DeterminismClass = DeterminismClass.STOCHASTIC
    side_effects: SideEffectClass = SideEffectClass.PURE
    latency: LatencyClass = LatencyClass.FAST
    tags: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    deprecated: bool = False
