"""Tool executor (RFC-1009 simplified).

Executes tools with permission checking and timeout handling.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from noesium.core.exceptions import ToolPermissionError, ToolTimeoutError

from .atomic import AtomicTool, ToolContext


class ToolExecutor:
    """Executes tools with permission checking and timeout handling.

    Note: Event emission has been removed as part of RFC-1009 simplification.
    Use ProgressEvent for observability instead.
    """

    def __init__(self) -> None:
        pass  # No event_store or bridge needed

    async def run(
        self,
        tool: AtomicTool,
        context: ToolContext,
        **kwargs: Any,
    ) -> Any:
        """Execute a tool with permission checking and timeout.

        Args:
            tool: The atomic tool to execute
            context: Tool execution context with permissions
            **kwargs: Tool arguments

        Returns:
            Tool execution result

        Raises:
            ToolPermissionError: If required permissions not granted
            ToolTimeoutError: If tool execution exceeds timeout
        """
        self._check_permissions(tool, context)

        time.monotonic()
        try:
            result = await asyncio.wait_for(
                tool.execute(**kwargs),
                timeout=tool.timeout_ms / 1000.0,
            )
            return result

        except asyncio.TimeoutError:
            raise ToolTimeoutError(f"Tool {tool.name} timed out after {tool.timeout_ms}ms")

    def _check_permissions(self, tool: AtomicTool, context: ToolContext) -> None:
        """Check if context has required permissions for tool."""
        missing = set(tool.permissions) - set(context.granted_permissions)
        if missing:
            raise ToolPermissionError(
                f"Tool {tool.name} requires permissions {missing} " f"not granted to agent {context.agent_id}"
            )
