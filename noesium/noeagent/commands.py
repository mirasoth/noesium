"""Subagent selection and display name normalization for NoeAgent.

This module provides:
1. Explicit subagent selection: subagent names, numeric prefix parsing (TUI), and
   InlineCommand building (inline_command_from_subagent) for astream_progress.
2. Display name normalization for toolkits and subagents.
"""

from __future__ import annotations

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
# Explicit subagent selection (no slash parsing)
# ---------------------------------------------------------------------------


class SubagentCommandType(str, Enum):
    """Types of subagent commands (for display and InlineCommand)."""

    BROWSER = "browser"
    RESEARCH = "research"
    CLAUDE = "claude"


@dataclass
class InlineCommand:
    """Explicit subagent invocation: (subagent_name, message). Built via inline_command_from_subagent."""

    command_type: SubagentCommandType
    subagent_name: str  # Technical name (e.g., "browser_use", "tacitus")
    message: str  # The message/task for the subagent
    original_input: str  # For display (e.g. "/research <message>")


# Map technical subagent name to command type (for explicit invocation)
_SUBAGENT_NAME_TO_COMMAND_TYPE: dict[str, SubagentCommandType] = {
    "browser_use": SubagentCommandType.BROWSER,
    "tacitus": SubagentCommandType.RESEARCH,
    "claude": SubagentCommandType.CLAUDE,
}

# Ordered list for TUI selector (1=Main, 2=Browser, 3=Research, 4=Claude)
BUILTIN_SUBAGENT_NAMES: list[str] = list(_SUBAGENT_NAME_TO_COMMAND_TYPE.keys())


def parse_subagent_selector(prefix: str) -> list[str]:
    """Parse a selector string into a list of valid subagent names.

    Accepts comma- or space-separated numbers: 1=Main (empty), 2=browser_use,
    3=tacitus, 4=claude. Unknown numbers are skipped.

    Returns:
        List of technical subagent names (may be empty for Main).
    """
    names: list[str] = []
    for part in prefix.replace(",", " ").split():
        part = part.strip()
        if not part or not part.isdigit():
            continue
        idx = int(part)
        if idx == 1:
            continue  # Main
        if 2 <= idx <= len(BUILTIN_SUBAGENT_NAMES) + 1:
            names.append(BUILTIN_SUBAGENT_NAMES[idx - 2])
    return list(dict.fromkeys(names))  # preserve order, dedupe


def validate_subagent_names(candidates: list[str]) -> list[str]:
    """Return only known built-in subagent names from the list."""
    known = set(_SUBAGENT_NAME_TO_COMMAND_TYPE)
    return [n for n in candidates if n in known]


def parse_subagent_prefix_from_input(user_input: str) -> tuple[list[str], str]:
    """Parse leading numeric selector from input; return (subagent_names, message).

    Leading tokens that are digits or comma-separated digits (e.g. "2", "3", "2,3")
    are treated as subagent selector (1=Main, 2=Browser, 3=Research, 4=Claude).
    The rest is the message. If no leading digits, returns ([], user_input).

    Examples:
        "2 3 雪球" -> (["browser_use", "tacitus"], "雪球")
        "2 雪球" -> (["browser_use"], "雪球")
        "雪球" -> ([], "雪球")
    """
    tokens = user_input.strip().split()
    i = 0
    while i < len(tokens) and tokens[i].replace(",", "").strip().isdigit():
        i += 1
    if i == 0:
        return ([], user_input.strip())
    prefix_str = " ".join(tokens[:i])
    message = " ".join(tokens[i:]).strip()
    names = parse_subagent_selector(prefix_str)
    return (names, message)


def inline_command_from_subagent(subagent_name: str, message: str) -> InlineCommand:
    """Build an InlineCommand from explicit (subagent_name, message). No slash parsing.

    Use this when the client has already chosen the subagent (e.g. UI dropdown,
    API field) so the message is never parsed for /command.

    Args:
        subagent_name: Technical name (e.g. "browser_use", "tacitus", "claude")
        message: Task message for the subagent

    Returns:
        InlineCommand with inferred command_type

    Raises:
        ValueError: If subagent_name is not a known built-in subagent
    """
    message = message.strip()
    cmd_type = _SUBAGENT_NAME_TO_COMMAND_TYPE.get(subagent_name)
    if cmd_type is None:
        raise ValueError(f"Unknown subagent '{subagent_name}'. Known: {list(_SUBAGENT_NAME_TO_COMMAND_TYPE.keys())}")
    return InlineCommand(
        command_type=cmd_type,
        subagent_name=subagent_name,
        message=message,
        original_input=f"/{cmd_type.value} {message}",
    )


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
