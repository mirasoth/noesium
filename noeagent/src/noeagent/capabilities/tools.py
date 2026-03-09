"""Tool capability setup for NoeAgent.

Handles toolkit loading, tool registration, and MCP server integration.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from noesium.core.capability.providers import ToolCapabilityProvider
from noesium.core.toolify.adapters.builtin_adapter import BuiltinAdapter
from noesium.core.toolify.adapters.function_adapter import FunctionAdapter
from noesium.core.toolify.atomic import ToolContext, ToolPermission
from noesium.core.toolify.base import AsyncBaseToolkit
from noesium.core.toolify.config import ToolkitConfig
from noesium.core.toolify.executor import ToolExecutor
from noesium.core.toolify.registry import ToolkitRegistry

if TYPE_CHECKING:
    from noesium.core.capability.registry import CapabilityRegistry

logger = logging.getLogger(__name__)


# Per-toolkit session-scoped directory overrides
_SESSION_DIR_OVERRIDES: dict[str, dict[str, str]] = {
    "document": {"cache_dir": "cache", "download_dir": "downloads"},
    "audio": {"cache_dir": "cache", "download_dir": "downloads"},
    "tabular_data": {"cache_dir": "cache"},
    "python_executor": {"default_workdir": "workdir"},
    "arxiv": {"default_download_dir": "papers"},
    "bash": {"workspace_root": "workspace"},
    "memory": {"storage_dir": "storage"},
    "file_edit": {"work_dir": "workspace"},
}


async def setup_tools(
    registry: "CapabilityRegistry",
    agent_id: str,
    enabled_toolkits: list[str],
    permissions: list[str],
    working_directory: str | None,
    session_dir: str,
    toolkit_configs: dict[str, dict[str, Any]],
    custom_tools: list[Any],
    mcp_servers: list[dict[str, Any]],
) -> tuple[ToolExecutor, ToolContext]:
    """Load and register tool capabilities.

    Args:
        registry: Capability registry to register tools
        agent_id: Agent identifier
        enabled_toolkits: List of toolkit names to load
        permissions: Granted tool permissions
        working_directory: Working directory for tools
        session_dir: Session directory for toolkits
        toolkit_configs: Per-toolkit configuration overrides
        custom_tools: Custom tool functions to register
        mcp_servers: MCP server configurations to load

    Returns:
        Tuple of (tool_executor, tool_context)
    """
    tool_executor = ToolExecutor()

    tool_context = ToolContext(
        agent_id=agent_id,
        granted_permissions=[ToolPermission(p) for p in permissions],
        working_directory=working_directory,
    )

    work_dir = working_directory or os.getcwd()
    toolkit_session_base = Path(session_dir) / "toolkits"

    async def _load_toolkit(toolkit_name: str) -> list:
        """Load a single toolkit and return its providers."""
        try:
            base_config: dict[str, Any] = {
                "workspace_root": work_dir,
                "work_dir": work_dir,
            }
            overrides = _SESSION_DIR_OVERRIDES.get(toolkit_name)
            if overrides:
                toolkit_session_dir = toolkit_session_base / toolkit_name
                for key, subdir in overrides.items():
                    base_config[key] = str(toolkit_session_dir / subdir)

            # Merge toolkit-specific config
            toolkit_specific_config = toolkit_configs.get(toolkit_name, {})
            base_config.update(toolkit_specific_config)

            toolkit_config = ToolkitConfig(
                name=toolkit_name,
                config=base_config,
            )
            toolkit = ToolkitRegistry.create_toolkit(toolkit_name, toolkit_config)
            if isinstance(toolkit, AsyncBaseToolkit):
                await toolkit.build()
            tools = await BuiltinAdapter.from_toolkit(toolkit, toolkit_name)
            providers = []
            for tool in tools:
                provider = ToolCapabilityProvider(tool, tool_executor, tool_context)
                providers.append(provider)
            return providers
        except Exception as exc:
            logger.warning("Failed to load toolkit %s: %s", toolkit_name, exc)
            return []

    # Load all toolkits concurrently
    if enabled_toolkits:
        toolkit_tasks = [_load_toolkit(name) for name in enabled_toolkits]
        toolkit_results = await asyncio.gather(*toolkit_tasks, return_exceptions=True)

        # Register all providers from successfully loaded toolkits
        for result in toolkit_results:
            if isinstance(result, list):
                for provider in result:
                    registry.register(provider)

    # Load MCP servers if configured
    if mcp_servers:
        await _setup_mcp_servers(registry, tool_executor, tool_context, mcp_servers)

    # Register custom tools
    for func in custom_tools:
        tool = FunctionAdapter.from_function(func)
        provider = ToolCapabilityProvider(tool, tool_executor, tool_context)
        registry.register(provider)

    return tool_executor, tool_context


async def _setup_mcp_servers(
    registry: "CapabilityRegistry",
    tool_executor: ToolExecutor,
    tool_context: ToolContext,
    mcp_servers: list[dict[str, Any]],
) -> None:
    """Load MCP server tools and register as capabilities.

    Args:
        registry: Capability registry
        tool_executor: Tool executor for MCP tools
        tool_context: Tool context for MCP tools
        mcp_servers: MCP server configurations
    """
    logger.info("Loading %d MCP server(s)...", len(mcp_servers))

    for mcp_config in mcp_servers:
        try:
            # MCP connection would happen here
            # For now, we'll import and use the MCP adapter
            pass

            # session = await _connect_mcp(mcp_config)
            # adapter = MCPAdapter(session)
            # mcp_tools = await adapter.discover_tools()
            # for tool in mcp_tools:
            #     provider = MCPCapabilityProvider(tool, tool_executor, tool_context)
            #     registry.register(provider)
            logger.info(
                "MCP server loading not yet implemented for %s",
                mcp_config.get("name", "unknown"),
            )
        except Exception as exc:
            logger.warning("Failed to load MCP server: %s", exc)


def register_subagent_tool(
    registry: "CapabilityRegistry",
    tool_executor: ToolExecutor,
    tool_context: ToolContext,
    agent: Any,  # NoeAgent instance
) -> None:
    """Register subagent spawn as a callable tool provider.

    Args:
        registry: Capability registry
        tool_executor: Tool executor
        tool_context: Tool context
        agent: NoeAgent instance for subagent spawning
    """
    from noeagent.config import NoeMode

    async def spawn_subagent(name: str, task: str, mode: str = "agent") -> str:
        """Spawn a child NoeAgent to work on a subtask autonomously and return its result.

        Args:
            name: Short identifier for the subagent (e.g. 'web-searcher', 'code-analyzer')
            task: The full task description to delegate to the child agent
            mode: 'agent' for full tool access, 'ask' for read-only Q&A
        """
        sid = await agent.spawn_subagent(name, mode=NoeMode(mode))
        return await agent.interact_with_subagent(sid, task)

    tool = FunctionAdapter.from_function(spawn_subagent)
    provider = ToolCapabilityProvider(tool, tool_executor, tool_context)
    registry.register(provider)
