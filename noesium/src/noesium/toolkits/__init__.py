"""Built-in toolkits for the Noesium framework.

This module provides access to all built-in toolkits. Toolkits inherit from
`noesium.core.toolify.BaseToolkit` and are registered automatically via the
`@register_toolkit` decorator.

Usage:
    from noesium.toolkits import get_toolkit, TOOLKIT_BASH

    # Get a specific toolkit
    bash_toolkit = get_toolkit(TOOLKIT_BASH)

    # Get all registered toolkits
    toolkits = get_toolkits_map()
"""

# Toolkit registration names (defined here, not in core)
TOOLKIT_ARXIV = "arxiv"
TOOLKIT_AUDIO = "audio"
TOOLKIT_BASH = "bash"
TOOLKIT_DOCUMENT = "document"
TOOLKIT_FILE_EDIT = "file_edit"
TOOLKIT_GITHUB = "github"
TOOLKIT_GMAIL = "gmail"
TOOLKIT_IMAGE = "image"
TOOLKIT_JINA_RESEARCH = "jina_research"
TOOLKIT_MCP = "mcp"
TOOLKIT_MEMORY = "memory"
TOOLKIT_PYTHON_EXECUTOR = "python_executor"
TOOLKIT_SERPER = "serper"
TOOLKIT_TABULAR_DATA = "tabular_data"
TOOLKIT_USER_INTERACTION = "user_interaction"
TOOLKIT_VIDEO = "video"
TOOLKIT_WEB_SEARCH = "web_search"
TOOLKIT_WIKIPEDIA = "wikipedia"

# Re-export toolkit registry functions from core
from noesium.core.toolify import (
    ToolkitRegistry,
    get_toolkit,
    get_toolkits_map,
)

__all__ = [
    # Registry functions
    "ToolkitRegistry",
    "get_toolkit",
    "get_toolkits_map",
    # Toolkit names
    "TOOLKIT_ARXIV",
    "TOOLKIT_AUDIO",
    "TOOLKIT_BASH",
    "TOOLKIT_DOCUMENT",
    "TOOLKIT_FILE_EDIT",
    "TOOLKIT_GITHUB",
    "TOOLKIT_GMAIL",
    "TOOLKIT_IMAGE",
    "TOOLKIT_JINA_RESEARCH",
    "TOOLKIT_MCP",
    "TOOLKIT_MEMORY",
    "TOOLKIT_PYTHON_EXECUTOR",
    "TOOLKIT_SERPER",
    "TOOLKIT_TABULAR_DATA",
    "TOOLKIT_USER_INTERACTION",
    "TOOLKIT_VIDEO",
    "TOOLKIT_WEB_SEARCH",
    "TOOLKIT_WIKIPEDIA",
]
