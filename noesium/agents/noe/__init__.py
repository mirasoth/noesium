"""Noe -- autonomous research assistant.

Two modes:
  * **Ask**: Single-turn Q&A, read-only, no tools.
  * **Agent**: Iterative planning, tool execution, reflection, memory persistence.
"""

from .agent import NoeAgent
from .config import NoeConfig, NoeMode

__all__ = [
    "NoeAgent",
    "NoeConfig",
    "NoeMode",
]
