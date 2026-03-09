"""Common tool utilities for agents.

This module provides a self-contained tool setup mechanism that can be used
by any agent (NoeAgent, subagents, or standalone agents) without dependencies.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from noesium.core.capability.registry import CapabilityRegistry
from noesium.core.capability.providers import ToolCapabilityProvider
from noesium.core.event.envelope import AgentRef
from noesium.core.event.store import InMemoryEventStore
from noesium.core.toolify.adapters.builtin_adapter import BuiltinAdapter
from noesium.core.toolify.atomic import ToolContext, ToolPermission
from noesium.core.toolify.executor import ToolExecutor
from noesium.core.toolify.registry import ToolkitRegistry

logger = logging.getLogger(__name__)


class ToolHelper:
    """Self-contained tool management for agents.

    Provides everything an agent needs to use tools:
    - ToolExecutor for execution
    - ToolContext for permissions
    - CapabilityRegistry for tool discovery
    - Simple API for tool execution
    """

    def __init__(
        self,
        agent_id: str,
        enabled_toolkits: list[str],
        permissions: list[str],
        working_directory: str | None = None,
        toolkit_configs: dict[str, dict[str, Any]] | None = None,
    ):
        """Initialize tool infrastructure.

        Args:
            agent_id: Unique agent identifier
            enabled_toolkits: List of toolkit names to load
            permissions: List of permission strings (e.g., ["fs:read", "env:read"])
            working_directory: Working directory for tools
            toolkit_configs: Per-toolkit configuration overrides
        """
        self.agent_id = agent_id
        self.enabled_toolkits = enabled_toolkits
        self.permissions = permissions
        self.working_directory = working_directory or os.getcwd()
        self.toolkit_configs = toolkit_configs or {}

        # Will be initialized
        self.tool_executor: ToolExecutor | None = None
        self.tool_context: ToolContext | None = None
        self.registry: CapabilityRegistry | None = None

        # Setup is deferred to async method
        self._initialized = False

    async def setup(self) -> None:
        """Initialize tool infrastructure (must be called before using tools)."""
        if self._initialized:
            return

        # Create event store
        event_store = InMemoryEventStore()
        producer = AgentRef(agent_id=self.agent_id, agent_type="subagent")

        # Create tool executor
        self.tool_executor = ToolExecutor(
            event_store=event_store,
            producer=producer,
        )

        # Create tool context with permissions
        self.tool_context = ToolContext(
            agent_id=self.agent_id,
            granted_permissions=[ToolPermission(p) for p in self.permissions],
            working_directory=self.working_directory,
        )

        # Create registry
        self.registry = CapabilityRegistry()

        # Load toolkits
        await self._load_toolkits()

        self._initialized = True
        logger.info(f"ToolHelper initialized for {self.agent_id} with {len(self.enabled_toolkits)} toolkits")

    async def _load_toolkits(self) -> None:
        """Load enabled toolkits into registry."""
        for toolkit_name in self.enabled_toolkits:
            try:
                # Get toolkit config
                config = self.toolkit_configs.get(toolkit_name, {})
                config.setdefault("workspace_root", self.working_directory)
                config.setdefault("work_dir", self.working_directory)

                # Create toolkit
                toolkit = ToolkitRegistry.create_toolkit(toolkit_name, config)

                # Convert toolkit to atomic tools
                tools = await BuiltinAdapter.from_toolkit(toolkit, toolkit_name)

                # Register each tool
                for tool in tools:
                    provider = ToolCapabilityProvider(
                        tool=tool,
                        executor=self.tool_executor,
                        context=self.tool_context,
                    )
                    self.registry.register(provider)

                logger.debug(f"Loaded toolkit '{toolkit_name}' with {len(tools)} tools")

            except Exception as e:
                logger.warning(f"Failed to load toolkit '{toolkit_name}': {e}")

    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """Execute a tool by name.

        Args:
            tool_name: Tool name (e.g., "file_edit:read_file")
            **kwargs: Tool arguments

        Returns:
            Tool execution result

        Raises:
            RuntimeError: If tools not initialized
            ValueError: If tool not found
            ToolPermissionError: If permission denied
        """
        if not self._initialized or not self.tool_executor or not self.tool_context or not self.registry:
            raise RuntimeError("ToolHelper not initialized. Call setup() first.")

        # Find tool in registry
        provider = self.registry.get_by_name(tool_name)
        if not provider:
            raise ValueError(f"Tool '{tool_name}' not found in registry")

        # Get the AtomicTool
        tool = provider._tool

        # Execute
        return await self.tool_executor.run(tool, self.tool_context, **kwargs)

    def get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions for prompts.

        Returns:
            Markdown-formatted list of available tools
        """
        if not self.registry:
            return "No tools available."

        providers = self.registry.list_providers()
        if not providers:
            return "No tools available."

        lines = []
        for provider in providers:
            desc = provider.descriptor
            name = desc.capability_id
            description = desc.description.split("\n")[0] if desc.description else ""

            # Format parameters if available
            schema = desc.input_schema or {}
            props = schema.get("properties", {})
            params = ""
            if props:
                param_list = [f"{k}: {v.get('type', 'any')}" for k, v in props.items()]
                params = f" ({', '.join(param_list)})"

            lines.append(f"- **{name}**: {description}{params}")

        return "\n".join(lines)

    def list_tools(self) -> list[dict[str, Any]]:
        """List available tools.

        Returns:
            List of tool descriptors
        """
        if not self.registry:
            return []

        tools = []
        for provider in self.registry.list_providers():
            desc = provider.descriptor
            tools.append({
                "name": desc.capability_id,
                "description": desc.description,
                "input_schema": desc.input_schema,
            })

        return tools


async def create_tool_helper(
    agent_id: str,
    enabled_toolkits: list[str],
    permissions: list[str],
    working_directory: str | None = None,
    toolkit_configs: dict[str, dict[str, Any]] | None = None,
) -> ToolHelper:
    """Factory function to create and initialize a ToolHelper.

    Args:
        agent_id: Unique agent identifier
        enabled_toolkits: List of toolkit names
        permissions: List of permission strings
        working_directory: Working directory
        toolkit_configs: Toolkit configurations

    Returns:
        Initialized ToolHelper instance
    """
    helper = ToolHelper(
        agent_id=agent_id,
        enabled_toolkits=enabled_toolkits,
        permissions=permissions,
        working_directory=working_directory,
        toolkit_configs=toolkit_configs,
    )
    await helper.setup()
    return helper