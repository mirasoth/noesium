"""Inline command parser and display name normalization for NoeAgent.

This module provides:
1. Inline command parsing for triggering subagents (/browser, /research, /claude)
2. Display name normalization for toolkits and subagents
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .agent import NoeAgent

# ---------------------------------------------------------------------------
# Display Name Mappings
# ---------------------------------------------------------------------------

# Toolkit display names: technical_name -> (DisplayName, description)
TOOLKIT_DISPLAY_NAMES: dict[str, tuple[str, str]] = {
    # Search & Research
    "web_search": ("WebSearch", "Web search with multiple engines"),
    "jina_research": ("JinaResearch", "Jina AI research tools"),
    "arxiv": ("ArXiv", "Academic paper search"),
    "serper": ("Serper", "Google search via Serper API"),
    "wikipedia": ("Wikipedia", "Wikipedia search and retrieval"),
    # File & Code
    "file_edit": ("File", "File editing operations"),
    "bash": ("Bash", "Shell command execution"),
    "python_executor": ("Python", "Python code execution"),
    # Data Processing
    "document": ("Document", "Document processing (PDF, Word)"),
    "tabular_data": ("Data", "CSV/Excel data processing"),
    "image": ("Image", "Image processing and generation"),
    "video": ("Video", "Video processing"),
    "audio": ("Audio", "Audio processing"),
    "audio_aliyun": ("AliyunAudio", "Aliyun audio services (TTS/STT)"),
    # External Services
    "github": ("GitHub", "GitHub API operations"),
    "gmail": ("Gmail", "Email operations"),
    # Agent Utilities
    "memory": ("Memory", "Memory management"),
    "user_interaction": ("UserInteraction", "User input/output"),
}

# Subagent display names: technical_name -> DisplayName
SUBAGENT_DISPLAY_NAMES: dict[str, str] = {
    "browser_use": "BrowserUse",
    "tacitus": "Tacitus",
    "claude": "Claude",
    "askura": "Askura",
}


def get_toolkit_display_name(technical_name: str) -> str:
    """Get the display name for a toolkit.

    Args:
        technical_name: The technical/registration name of the toolkit

    Returns:
        Display name (PascalCase) for the toolkit
    """
    if technical_name in TOOLKIT_DISPLAY_NAMES:
        return TOOLKIT_DISPLAY_NAMES[technical_name][0]
    # Fallback: Convert snake_case to PascalCase
    return "".join(word.capitalize() for word in technical_name.split("_"))


def get_toolkit_technical_name(display_name: str) -> Optional[str]:
    """Get the technical name from a display name.

    Args:
        display_name: The display name of the toolkit

    Returns:
        Technical name or None if not found
    """
    display_lower = display_name.lower()
    for tech_name, (disp_name, _) in TOOLKIT_DISPLAY_NAMES.items():
        if disp_name.lower() == display_lower or tech_name == display_lower:
            return tech_name
    return None


def get_subagent_display_name(technical_name: str) -> str:
    """Get the display name for a subagent.

    Args:
        technical_name: The technical name of the subagent

    Returns:
        Display name (PascalCase) for the subagent
    """
    return SUBAGENT_DISPLAY_NAMES.get(technical_name, technical_name.replace("_", " ").title().replace(" ", ""))


def get_subagent_technical_name(display_name: str) -> Optional[str]:
    """Get the technical name from a display name.

    Args:
        display_name: The display name of the subagent

    Returns:
        Technical name or None if not found
    """
    display_lower = display_name.lower()
    for tech_name, disp_name in SUBAGENT_DISPLAY_NAMES.items():
        if disp_name.lower() == display_lower or tech_name == display_lower:
            return tech_name
    return None


# ---------------------------------------------------------------------------
# Inline Command System
# ---------------------------------------------------------------------------


class SubagentCommandType(str, Enum):
    """Types of subagent commands."""

    BROWSER = "browser"
    RESEARCH = "research"
    CLAUDE = "claude"


@dataclass
class InlineCommand:
    """Parsed inline command from user input."""

    command_type: SubagentCommandType
    subagent_name: str  # Technical name (e.g., "browser_use", "tacitus")
    message: str  # The message/task for the subagent
    original_input: str  # The original user input


# Command patterns and their mappings
# Format: (command_pattern, SubagentCommandType, technical_subagent_name)
SUBAGENT_COMMANDS: list[tuple[str, SubagentCommandType, str]] = [
    ("/browser", SubagentCommandType.BROWSER, "browser_use"),
    ("/deep_research", SubagentCommandType.RESEARCH, "tacitus"),
    ("/research", SubagentCommandType.RESEARCH, "tacitus"),
    ("/claude", SubagentCommandType.CLAUDE, "claude"),
]

# Build regex pattern for command detection
# Matches: /command <rest of message>
_COMMAND_PATTERN = re.compile(
    r"^(" + "|".join(re.escape(cmd) for cmd, _, _ in SUBAGENT_COMMANDS) + r")\s*(.*)", re.IGNORECASE | re.DOTALL
)


def parse_inline_command(user_input: str) -> Optional[InlineCommand]:
    """Parse an inline command from user input.

    Inline commands start with a forward slash and specify which subagent to use.
    The rest of the input becomes the task for that subagent.

    Supported commands:
    - /browser <task> - Trigger BrowserUse subagent (OPTIONAL - can also be auto-triggered)
    - /research <task> - Trigger Tacitus research subagent (MUST use command)
    - /deep_research <task> - Alias for /research
    - /claude <task> - Trigger Claude subagent (OPTIONAL)

    Args:
        user_input: The raw user input

    Returns:
        InlineCommand if a command was found, None otherwise
    """
    user_input = user_input.strip()
    if not user_input.startswith("/"):
        return None

    match = _COMMAND_PATTERN.match(user_input)
    if not match:
        return None

    command_str = match.group(1).lower()
    message = match.group(2).strip()

    # Find the matching command
    for cmd_pattern, cmd_type, subagent_name in SUBAGENT_COMMANDS:
        if command_str == cmd_pattern.lower():
            return InlineCommand(
                command_type=cmd_type,
                subagent_name=subagent_name,
                message=message,
                original_input=user_input,
            )

    return None


def is_subagent_command(user_input: str) -> bool:
    """Check if user input contains a subagent command.

    Args:
        user_input: The raw user input

    Returns:
        True if the input starts with a subagent command
    """
    return parse_inline_command(user_input) is not None


async def execute_subagent_command(
    agent: "NoeAgent",
    command: InlineCommand,
) -> tuple[bool, str]:
    """Execute a subagent command.

    This function directly invokes the specified subagent with the given message,
    bypassing the normal LLM-based routing.

    Args:
        agent: The NoeAgent instance
        command: The parsed inline command

    Returns:
        Tuple of (success, result_or_error_message)
    """

    # Ensure agent is initialized
    await agent.initialize()

    subagent_name = command.subagent_name
    message = command.message

    if not message:
        return (
            False,
            f"No task provided for {get_subagent_display_name(subagent_name)}. Usage: /{command.command_type.value} <your task>",
        )

    # Try to find the subagent in the registry
    registry = agent._registry
    if registry is None:
        return False, "Agent not properly initialized (no capability registry)"

    # Check if it's a built-in subagent
    cap_id = f"builtin_agent:{subagent_name}"
    try:
        provider = registry.get_by_name(cap_id)
    except Exception:
        provider = None

    if provider is None:
        # Check if the subagent is configured but not enabled
        enabled_subagents = agent.config.get_enabled_builtin_subagents()
        subagent_names = [s.agent_type for s in enabled_subagents]
        if subagent_name not in subagent_names:
            return (
                False,
                f"Subagent '{get_subagent_display_name(subagent_name)}' is not enabled. Enable it in your config.",
            )
        return False, f"Subagent '{get_subagent_display_name(subagent_name)}' not found in registry."

    try:
        # Use streaming if available for real-time progress
        if hasattr(provider, "invoke_streaming"):
            result = await agent.execute_builtin_subagent_streaming(provider, message, subagent_name)
        else:
            result = await provider.invoke(message=message)
        return True, str(result)
    except Exception as exc:
        return False, f"Error executing {get_subagent_display_name(subagent_name)}: {exc}"


# ---------------------------------------------------------------------------
# TUI Command Help
# ---------------------------------------------------------------------------


def get_subagent_commands_help() -> dict[str, str]:
    """Get help text for all subagent commands.

    Returns:
        Dict mapping command to description
    """
    return {
        "/browser": f"Trigger {get_subagent_display_name('browser_use')} for web automation",
        "/research": f"Trigger {get_subagent_display_name('tacitus')} for deep research",
        "/deep_research": f"Alias for /research",
        "/claude": f"Trigger {get_subagent_display_name('claude')} subagent",
    }
