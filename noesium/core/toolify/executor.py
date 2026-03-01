"""Event-wrapped tool executor (RFC-2004 §5)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from noesium.core.event.envelope import AgentRef, TraceContext
from noesium.core.event.store import EventStore
from noesium.core.event.types import DomainEvent
from noesium.core.exceptions import ToolPermissionError, ToolTimeoutError
from noesium.core.msgbus.bridge import EnvelopeBridge

from .atomic import AtomicTool, ToolContext
from .tool_events import ToolCompleted, ToolFailed, ToolInvoked, ToolTimeout


class ToolExecutor:
    """Wraps every tool invocation with lifecycle events.

    Emits tool.invoked before execution and tool.completed / tool.failed /
    tool.timeout after.  If no event_store is configured, events are silently
    dropped (useful for lightweight setups).
    """

    def __init__(
        self,
        event_store: EventStore | None = None,
        bridge: EnvelopeBridge | None = None,
        producer: AgentRef | None = None,
    ) -> None:
        self._event_store = event_store
        self._bridge = bridge
        self._producer = producer or AgentRef(agent_id="system", agent_type="tool_executor")

    async def run(
        self,
        tool: AtomicTool,
        context: ToolContext,
        **kwargs: Any,
    ) -> Any:
        self._check_permissions(tool, context)

        invoked_event = ToolInvoked(
            tool_id=tool.tool_id,
            tool_name=tool.name,
            input_data=kwargs,
            source=tool.source.value,
        )
        await self._emit(invoked_event, context.trace)

        t0 = time.monotonic()
        try:
            result = await asyncio.wait_for(
                tool.execute(**kwargs),
                timeout=tool.timeout_ms / 1000.0,
            )
            duration_ms = int((time.monotonic() - t0) * 1000)

            completed_event = ToolCompleted(
                tool_id=tool.tool_id,
                tool_name=tool.name,
                output_data=result,
                duration_ms=duration_ms,
            )
            await self._emit(completed_event, context.trace)
            return result

        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - t0) * 1000)
            timeout_event = ToolTimeout(
                tool_id=tool.tool_id,
                tool_name=tool.name,
                timeout_ms=tool.timeout_ms,
            )
            await self._emit(timeout_event, context.trace)
            raise ToolTimeoutError(f"Tool {tool.name} timed out after {tool.timeout_ms}ms")

        except ToolTimeoutError:
            raise

        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            failed_event = ToolFailed(
                tool_id=tool.tool_id,
                tool_name=tool.name,
                error=str(e),
                duration_ms=duration_ms,
            )
            await self._emit(failed_event, context.trace)
            raise

    def _check_permissions(self, tool: AtomicTool, context: ToolContext) -> None:
        missing = set(tool.permissions) - set(context.granted_permissions)
        if missing:
            raise ToolPermissionError(
                f"Tool {tool.name} requires permissions {missing} " f"not granted to agent {context.agent_id}"
            )

    async def _emit(self, event: DomainEvent, trace: TraceContext) -> None:
        if self._event_store is None:
            return
        envelope = event.to_envelope(producer=self._producer, trace=trace)
        await self._event_store.append(envelope)
        if self._bridge:
            await self._bridge.publish(envelope)
