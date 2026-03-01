"""RFC-0002 compliant event envelope and identity models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from uuid_extensions import uuid7str


def _uuid7_str() -> str:
    return uuid7str()


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


class AgentRef(BaseModel):
    """Producer identity (RFC-0002 Section 5)."""

    agent_id: str
    agent_type: str
    runtime_id: str = "local"
    instance_id: str = Field(default_factory=_uuid7_str)


class TraceContext(BaseModel):
    """Distributed trace propagation (RFC-0002 Section 6)."""

    trace_id: str = Field(default_factory=_uuid7_str)
    span_id: str = Field(default_factory=_uuid7_str)
    parent_span_id: str | None = None
    depth: int = 0

    def child(self) -> TraceContext:
        """Create a child span inheriting trace_id."""
        return TraceContext(
            trace_id=self.trace_id,
            parent_span_id=self.span_id,
            depth=self.depth + 1,
        )


class SignatureBlock(BaseModel):
    """Optional cryptographic signature (RFC-0002 Section 11)."""

    algorithm: str
    public_key_id: str
    signature: str


class EventEnvelope(BaseModel):
    """Canonical immutable event wrapper (RFC-0002 Section 3)."""

    spec_version: str = "1.0.0"
    event_id: str = Field(default_factory=_uuid7_str)
    event_type: str
    event_version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=_utc_now)
    producer: AgentRef
    trace: TraceContext
    causation_id: str | None = None
    correlation_id: str | None = None
    idempotency_key: str | None = None
    partition_key: str | None = None
    ttl_ms: int | None = None
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)
    signature: SignatureBlock | None = None
