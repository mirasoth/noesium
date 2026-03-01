"""Adapter for user-defined functions to AtomicTool (RFC-2004 §7.4)."""

from __future__ import annotations

from typing import Any, Callable

from noesium.core.toolify.adapters.builtin_adapter import _extract_schema
from noesium.core.toolify.atomic import AtomicTool, ToolSource


class FunctionAdapter:
    """Wraps a plain Python callable as an AtomicTool."""

    @staticmethod
    def from_function(
        func: Callable,
        name: str | None = None,
        description: str | None = None,
        **tool_kwargs: Any,
    ) -> AtomicTool:
        schema = _extract_schema(func)
        tool = AtomicTool(
            name=name or func.__name__,
            description=description or func.__doc__ or "",
            input_schema=schema,
            source=ToolSource.USER,
            tags=["source:user"],
            **tool_kwargs,
        ).bind(func)
        return tool
