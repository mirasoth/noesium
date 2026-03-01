"""Capability-based tool registry (RFC-2004 §8)."""

from __future__ import annotations

import logging
from typing import Any

from noesium.core.exceptions import ToolNotFoundError

from .atomic import AtomicTool, ToolSource

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Manages AtomicTool instances for capability-based discovery.

    Integrates with the existing ToolkitRegistry to wrap built-in toolkits
    as AtomicTools, and supports MCP server tools and user functions.
    """

    def __init__(self) -> None:
        self._tools: dict[str, AtomicTool] = {}
        self._by_name: dict[str, AtomicTool] = {}

    def register(self, tool: AtomicTool) -> None:
        self._tools[tool.tool_id] = tool
        self._by_name[tool.name] = tool

    def register_many(self, tools: list[AtomicTool]) -> None:
        for tool in tools:
            self.register(tool)

    def get_by_id(self, tool_id: str) -> AtomicTool:
        if tool_id not in self._tools:
            raise ToolNotFoundError(f"Tool id '{tool_id}' not registered")
        return self._tools[tool_id]

    def get_by_name(self, name: str) -> AtomicTool:
        if name not in self._by_name:
            raise ToolNotFoundError(f"Tool '{name}' not registered")
        return self._by_name[name]

    def list_tools(
        self,
        source: ToolSource | None = None,
        tags: list[str] | None = None,
    ) -> list[AtomicTool]:
        tools = list(self._tools.values())
        if source:
            tools = [t for t in tools if t.source == source]
        if tags:
            tools = [t for t in tools if all(tag in t.tags for tag in tags)]
        return tools

    def load_builtin_toolkits(self, toolkit_names: list[str] | None = None) -> None:
        """Discover and wrap existing registered toolkits as AtomicTools."""
        from noesium.core.toolify.adapters.builtin_adapter import BuiltinAdapter
        from noesium.core.toolify.registry import ToolkitRegistry

        names = toolkit_names or ToolkitRegistry.list_toolkits()
        for name in names:
            try:
                toolkit = ToolkitRegistry.create_toolkit(name)
                atomic_tools = BuiltinAdapter.from_toolkit(toolkit, name)
                self.register_many(atomic_tools)
            except Exception as exc:
                logger.debug("Skipping toolkit %s: %s", name, exc)

    async def load_mcp_server(self, session: Any) -> list[AtomicTool]:
        from noesium.core.toolify.adapters.mcp_adapter import MCPAdapter

        adapter = MCPAdapter(session)
        tools = await adapter.discover_tools()
        self.register_many(tools)
        return tools

    def to_langchain_tools(self, names: list[str] | None = None) -> list[Any]:
        """Convert registered AtomicTools to LangChain BaseTool format."""
        from noesium.core.toolify.base import ToolConverter

        tools = self.list_tools() if names is None else [self.get_by_name(n) for n in names]
        lc_tools: list[Any] = []
        for t in tools:
            if t._callable is not None:
                lc_tools.append(ToolConverter.function_to_langchain(t._callable, t.name, t.description))
        return lc_tools
