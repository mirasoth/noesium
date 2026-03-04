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
from .commands import (
    InlineCommand,
    SubagentCommandType,
    execute_subagent_command,
    get_subagent_commands_help,
    get_subagent_display_name,
    get_toolkit_display_name,
    is_subagent_command,
    parse_inline_command,
)
from .config import CliSubagentConfig, NoeConfig, NoeMode
from .progress import ProgressCallback, ProgressEvent, ProgressEventType
from .schemas import AgentAction, SubagentAction, ToolCallAction
from .session_log import SessionLogger
from .state import TaskPlan, TaskStep

__all__ = [
    "NoeAgent",
    "NoeConfig",
    "NoeMode",
    "CliSubagentConfig",
    "AgentAction",
    "SubagentAction",
    "ToolCallAction",
    "TaskPlan",
    "TaskStep",
    "ProgressEvent",
    "ProgressEventType",
    "ProgressCallback",
    "SessionLogger",
    # Commands module
    "InlineCommand",
    "SubagentCommandType",
    "parse_inline_command",
    "is_subagent_command",
    "execute_subagent_command",
    "get_subagent_commands_help",
    "get_toolkit_display_name",
    "get_subagent_display_name",
]
