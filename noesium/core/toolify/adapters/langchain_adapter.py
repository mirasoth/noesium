"""Adapter for LangChain BaseTool to AtomicTool (RFC-2004 §7.2)."""

from __future__ import annotations

from typing import Any

from noesium.core.toolify.atomic import AtomicTool, ToolSource

try:
    from langchain_core.tools import BaseTool
except ImportError:  # pragma: no cover
    BaseTool = None  # type: ignore[assignment,misc]


class LangChainAdapter:
    """Wraps LangChain BaseTool instances as AtomicTool."""

    @staticmethod
    def from_langchain_tool(lc_tool: Any) -> AtomicTool:
        schema: dict[str, Any] = {}
        if hasattr(lc_tool, "args_schema") and lc_tool.args_schema is not None:
            schema = lc_tool.args_schema.model_json_schema()

        tool = AtomicTool(
            name=lc_tool.name,
            description=lc_tool.description or "",
            input_schema=schema,
            source=ToolSource.LANGCHAIN,
            tags=["source:langchain"],
        )

        if hasattr(lc_tool, "ainvoke"):
            tool.bind(lc_tool.ainvoke)
        else:
            tool.bind(lc_tool.invoke)
        return tool

    @staticmethod
    def from_langchain_tools(tools: list[Any]) -> list[AtomicTool]:
        return [LangChainAdapter.from_langchain_tool(t) for t in tools]
