"""Noe -- autonomous research assistant.

Two modes:
  * **Ask**: Single-turn Q&A, read-only, no tools.
  * **Agent**: Iterative planning, tool execution, reflection, memory persistence.
"""

# Automatically load .env file on module import
try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    # python-dotenv not installed, silently skip
    pass

from .agent import NoeAgent
from .config import NoeConfig, NoeMode
from .progress import ProgressCallback, ProgressEvent, ProgressEventType
from .schemas import AgentAction, SubagentAction, ToolCallAction
from .session_log import SessionLogger
from .state import TaskPlan, TaskStep

__all__ = [
    "NoeAgent",
    "NoeConfig",
    "NoeMode",
    "AgentAction",
    "SubagentAction",
    "ToolCallAction",
    "TaskPlan",
    "TaskStep",
    "ProgressEvent",
    "ProgressEventType",
    "ProgressCallback",
    "SessionLogger",
]
