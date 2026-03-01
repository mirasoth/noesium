"""Event serialization and canonicalization utilities."""

from __future__ import annotations

import json

from .envelope import EventEnvelope


def canonicalize(envelope: EventEnvelope) -> str:
    """Deterministic JSON serialization (sorted keys, no extra whitespace).

    Aligned with RFC 8785 (JSON Canonicalization Scheme) for signature
    computation boundaries.
    """
    data = json.loads(envelope.model_dump_json())
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def serialize(envelope: EventEnvelope) -> str:
    """Serialize an envelope to JSON string."""
    return envelope.model_dump_json()


def deserialize(raw: str) -> EventEnvelope:
    """Deserialize a JSON string to an EventEnvelope."""
    return EventEnvelope.model_validate_json(raw)
