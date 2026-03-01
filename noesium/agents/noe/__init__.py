"""Noet -- autonomous research assistant.

Two modes:
  * **Ask**: Single-turn Q&A, read-only, no tools.
  * **Agent**: Iterative planning, tool execution, reflection, memory persistence.
"""

from .agent import Noet
from .config import NoeConfig, NoeMode

__all__ = [
    "Noet",
    "NoeConfig",
    "NoeMode",
]
