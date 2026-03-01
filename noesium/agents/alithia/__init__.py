"""AlithiaAgent -- autonomous research assistant.

Two modes:
  * **Ask**: Single-turn Q&A, read-only, no tools.
  * **Agent**: Iterative planning, tool execution, reflection, memory persistence.
"""

from .agent import AlithiaAgent
from .config import AlithiaConfig, AlithiaMode

__all__ = [
    "AlithiaAgent",
    "AlithiaConfig",
    "AlithiaMode",
]
