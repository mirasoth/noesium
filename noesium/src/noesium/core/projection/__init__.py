"""Projection layer: deterministic state derivation from events (RFC-0004, RFC-1001)."""

from .base import BaseProjection, ProjectionEngine
from .cognitive import CognitiveProjection

__all__ = [
    "BaseProjection",
    "CognitiveProjection",
    "ProjectionEngine",
]
