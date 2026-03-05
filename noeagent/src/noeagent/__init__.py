"""Noe -- autonomous research assistant.

Two modes:
  * **Ask**: Single-turn Q&A, read-only, no tools.
  * **Agent**: Iterative planning, tool execution, reflection, memory persistence.
"""

# =============================================================================
# CRITICAL: Override NOESIUM_HOME BEFORE any other imports (RFC-1007)
# The noesium package exports NoeAgent, so it uses ~/.noeagent by default.
# For core-only usage, import directly from noesium.core instead.
# =============================================================================
from pathlib import Path

_NOEAGENT_HOME = Path.home() / ".noeagent"

# Import and call set_noesium_home before any other noesium module imports
from noesium.core.consts import set_noesium_home

set_noesium_home(_NOEAGENT_HOME)

# Automatically load .env file on module import
try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    # python-dotenv not installed, silently skip
    pass

from noesium.core.event import ProgressCallback, ProgressEvent, ProgressEventType

from .agent import NoeAgent
from .commands import (
    BUILTIN_SUBAGENT_NAMES,
    InlineCommand,
    SubagentCommandType,
    execute_subagent_command,
    get_subagent_display_name,
    get_toolkit_display_name,
    inline_command_from_subagent,
    parse_subagent_prefix_from_input,
    validate_subagent_names,
)
from .config import CliSubagentConfig, NoeConfig, NoeMode
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
    "BUILTIN_SUBAGENT_NAMES",
    "InlineCommand",
    "SubagentCommandType",
    "execute_subagent_command",
    "get_toolkit_display_name",
    "get_subagent_display_name",
    "inline_command_from_subagent",
    "parse_subagent_prefix_from_input",
    "validate_subagent_names",
]
