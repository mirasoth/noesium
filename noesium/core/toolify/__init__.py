"""
Noesium Tools Module

A unified toolkit system for LLM-based agents with support for:
- LangChain tool integration
- MCP (Model Context Protocol) support
- Unified configuration management
- Built-in logging and LLM integration
- AtomicTool abstraction and event-wrapped execution (RFC-2004)
"""

from .atomic import AtomicTool, ToolContext, ToolPermission, ToolSource
from .base import AsyncBaseToolkit, BaseToolkit
from .config import ToolkitConfig
from .executor import ToolExecutor
from .registry import ToolkitRegistry, get_toolkit, get_toolkits_map
from .skill import Skill, SkillRegistry
from .tool_registry import ToolRegistry

# Import MCP integration if available
try:
    pass

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

__all__ = [
    # Legacy (preserved)
    "AsyncBaseToolkit",
    "BaseToolkit",
    "ToolkitConfig",
    "ToolkitRegistry",
    "get_toolkit",
    "get_toolkits_map",
    "MCP_AVAILABLE",
    # Unified tool system (RFC-2004)
    "AtomicTool",
    "ToolContext",
    "ToolExecutor",
    "ToolPermission",
    "ToolRegistry",
    "ToolSource",
    "Skill",
    "SkillRegistry",
]
