"""Projection layer: deterministic state derivation from events (RFC-1002, RFC-1001)."""

from .base import BaseProjection, ProjectionEngine
from .cognitive import CognitiveProjection

__all__ = [
    "BaseProjection",
    "CognitiveProjection",
    "ProjectionEngine",
]
