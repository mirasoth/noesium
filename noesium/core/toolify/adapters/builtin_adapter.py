"""Adapter for converting existing noesium toolkits to AtomicTool (RFC-2004 §7.1)."""

from __future__ import annotations

import inspect
from typing import Any, Callable, get_type_hints

from noesium.core.toolify.atomic import AtomicTool, ToolSource


def _extract_schema(func: Callable) -> dict[str, Any]:
    """Best-effort JSON Schema extraction from function signature."""
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}
    sig = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        prop: dict[str, Any] = {}
        hint = hints.get(name)
        if hint is str or hint == "str":
            prop["type"] = "string"
        elif hint is int or hint == "int":
            prop["type"] = "integer"
        elif hint is float or hint == "float":
            prop["type"] = "number"
        elif hint is bool or hint == "bool":
            prop["type"] = "boolean"
        else:
            prop["type"] = "string"
        properties[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


class BuiltinAdapter:
    """Converts existing toolkit functions to AtomicTool instances."""

    @staticmethod
    def from_toolkit(
        toolkit: Any,
        toolkit_name: str,
    ) -> list[AtomicTool]:
        from noesium.core.toolify.base import AsyncBaseToolkit

        if isinstance(toolkit, AsyncBaseToolkit):
            tools_map = toolkit.get_tools_map_sync()
        else:
            tools_map = toolkit.get_filtered_tools_map()

        atomic_tools: list[AtomicTool] = []
        for name, func in tools_map.items():
            schema = _extract_schema(func)
            tool = AtomicTool(
                name=name,
                description=func.__doc__ or f"Tool: {name}",
                input_schema=schema,
                source=ToolSource.BUILTIN,
                toolkit_name=toolkit_name,
                tags=[f"source:builtin", f"toolkit:{toolkit_name}"],
            ).bind(func)
            atomic_tools.append(tool)
        return atomic_tools
