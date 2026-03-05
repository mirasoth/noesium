"""Adapter for MCP server tools to AtomicTool (RFC-2004 §7.3)."""

from __future__ import annotations

from typing import Any, Callable

from noesium.core.toolify.atomic import AtomicTool, ToolPermission, ToolSource


class MCPAdapter:
    """Discovers and wraps MCP server tools as AtomicTool instances."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def discover_tools(self) -> list[AtomicTool]:
        mcp_tools = await self._session.list_tools()
        atomic_tools: list[AtomicTool] = []
        for mcp_tool in mcp_tools:
            tool = AtomicTool(
                name=mcp_tool.name,
                description=mcp_tool.description or "",
                input_schema=getattr(mcp_tool, "inputSchema", None) or {},
                source=ToolSource.MCP,
                permissions=[ToolPermission.MCP_CONNECT],
                tags=["source:mcp"],
            )
            tool.bind(self._make_mcp_caller(mcp_tool.name))
            atomic_tools.append(tool)
        return atomic_tools

    def _make_mcp_caller(self, tool_name: str) -> Callable:
        async def _call(**kwargs: Any) -> Any:
            result = await self._session.call_tool(tool_name, kwargs)
            return result

        return _call
