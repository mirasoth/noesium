"""Tool execution event source (RFC-1007 §7.4)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from noeagent.autonomous.event_system import AutonomousEvent
from noeagent.autonomous.events.sources.base import BaseEventSource

if TYPE_CHECKING:
    from bubus import EventBus

    from noesium.core.capability.registry import CapabilityRegistry

logger = logging.getLogger(__name__)


class ToolObserverEventSource(BaseEventSource):
    """Observes tool execution and emits events.

    Monitors tool execution results and emits events when:
    - Tool produces significant output
    - Tool detects changes (new files, API changes)
    - Tool execution fails

    This enables reactive goal creation based on tool findings.

    Example:
        - Web search tool finds new papers → triggers "review papers" goal
        - File search finds changes → triggers "analyze changes" goal
        - Tool execution fails → triggers "handle error" goal
    """

    def __init__(self, event_bus: EventBus, capability_registry: CapabilityRegistry):
        """Initialize tool observer.

        Args:
            event_bus: EventBus to emit events to
            capability_registry: Registry to observe for tool executions
        """
        super().__init__(event_bus)
        self.registry = capability_registry
        self._observer_id: str | None = None
        self._subscribed = False

    async def start(self) -> None:
        """Start observing tool executions.

        Registers observer callback with capability registry.
        """
        if self._subscribed:
            return

        # Register execution observer if registry supports it
        if self.registry and hasattr(self.registry, "add_execution_observer"):
            self._observer_id = self.registry.add_execution_observer(self._on_tool_execution)

        self._subscribed = True
        self._running = True
        self.logger.info("ToolObserverEventSource started")

    def stop(self) -> None:
        """Stop observing tool executions."""
        self._running = False

        if self.registry and self._observer_id:
            if hasattr(self.registry, "remove_execution_observer"):
                self.registry.remove_execution_observer(self._observer_id)

        self._subscribed = False
        self.logger.info("ToolObserverEventSource stopped")

    async def _on_tool_execution(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_result: Any,
        success: bool,
    ) -> None:
        """Callback when tool execution completes.

        Args:
            tool_name: Name of the executed tool
            tool_input: Input parameters
            tool_result: Execution result
            success: Whether execution succeeded
        """
        if not self._running:
            return

        # Determine if this warrants an event
        if not self._should_emit_event(tool_name, tool_result, success):
            return

        # Create and emit event
        event = AutonomousEvent(
            type=f"tool.{tool_name}.executed",
            source="tool_observer",
            payload={
                "tool": tool_name,
                "input": self._sanitize_input(tool_input),
                "result": self._sanitize_result(tool_result),
                "success": success,
            },
        )

        await self._emit_event(event)

    def _should_emit_event(
        self,
        tool_name: str,
        result: Any,
        success: bool,
    ) -> bool:
        """Determine if tool execution should emit event.

        Args:
            tool_name: Tool name
            result: Execution result
            success: Success flag

        Returns:
            True if event should be emitted
        """
        # Always emit for failures
        if not success:
            return True

        # Emit for change-detecting tools
        change_detecting_tools = {
            "web_search",
            "github_search",
            "github_list_issues",
            "file_search",
            "list_directory",
            "read_file",
            "fetch_url",
        }

        return tool_name in change_detecting_tools

    def _sanitize_input(self, tool_input: dict) -> dict:
        """Sanitize tool input for event payload."""
        sanitized = {}
        for k, v in tool_input.items():
            if k in ("password", "token", "api_key", "secret"):
                sanitized[k] = "***REDACTED***"
            else:
                str_v = str(v)
                sanitized[k] = str_v[:200] if len(str_v) > 200 else v
        return sanitized

    def _sanitize_result(self, result: Any) -> str:
        """Sanitize tool result for event payload."""
        str_result = str(result)
        return str_result[:500] if len(str_result) > 500 else str_result
