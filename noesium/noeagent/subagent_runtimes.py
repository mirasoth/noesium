"""NoeAgent-specific subagent runtime implementations (RFC-1006 Section 6.2).

These runtimes implement the BaseSubagentRuntime interface for the different
subagent backends used by NoeAgent:
- NoeChildSubagentRuntime: In-process NoeAgent child agents
- NoeBuiltinSubagentRuntime: Built-in specialized agents (browser_use, tacitus)
- NoeCliSubagentRuntime: External CLI agents via ExternalCliAdapter

These classes live in the noeagent module (not core) because they have
NoeAgent-specific dependencies. They are registered with SubagentManager
during NoeAgent initialization.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, AsyncGenerator

from noesium.core.agent.subagent.descriptor import (
    BackendType,
    CostHint,
    LatencyHint,
    SubagentDescriptor,
)
from noesium.core.agent.subagent.events import SubagentErrorCode, SubagentProgressEvent
from noesium.core.agent.subagent.protocol import BaseSubagentRuntime

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class NoeChildSubagentRuntime(BaseSubagentRuntime):
    """Runtime adapter for in-process NoeAgent child agents (RFC-1006 §6.2).

    Wraps a child NoeAgent, translating its ProgressEvents into the
    standard SubagentProgressEvent stream. Shares registry and tool
    infrastructure with the parent agent.
    """

    def __init__(self, agent: Any, subagent_id: str) -> None:
        """Initialize with a child NoeAgent instance.

        Args:
            agent: The child NoeAgent instance.
            subagent_id: Stable identifier for this subagent.
        """
        self._agent = agent
        self._subagent_id = subagent_id
        self._descriptor = SubagentDescriptor(
            subagent_id=subagent_id,
            display_name=subagent_id,
            description=f"In-process NoeAgent child: {subagent_id}",
            backend_type=BackendType.INPROC,
            supports_streaming=True,
            cost_hint=CostHint.MEDIUM,
            latency_hint=LatencyHint.BATCH,
        )

    @classmethod
    def get_descriptor(cls) -> SubagentDescriptor:
        raise NotImplementedError("NoeChildSubagentRuntime uses instance-specific descriptors")

    @property
    def descriptor(self) -> SubagentDescriptor:
        return self._descriptor

    async def health(self) -> bool:
        return self._agent is not None

    async def execute(
        self,
        task: str,
        **kwargs: Any,
    ) -> AsyncGenerator[SubagentProgressEvent, None]:
        """Execute task by delegating to child NoeAgent.astream_progress."""
        request_id = kwargs.get("request_id", "unknown")

        yield SubagentProgressEvent.start(
            request_id=request_id,
            subagent_id=self._subagent_id,
            summary=f"Starting {self._subagent_id}",
        )

        try:
            from noesium.core.event import ProgressEventType

            final_text = ""
            async for event in self._agent.astream_progress(task):
                if event.type == ProgressEventType.FINAL_ANSWER:
                    final_text = event.text or ""
                elif event.type == ProgressEventType.THINKING:
                    yield SubagentProgressEvent.thought(
                        request_id=request_id,
                        subagent_id=self._subagent_id,
                        thought=event.summary or "",
                    )
                elif event.type not in (
                    ProgressEventType.SESSION_START,
                    ProgressEventType.SESSION_END,
                ):
                    yield SubagentProgressEvent.progress(
                        request_id=request_id,
                        subagent_id=self._subagent_id,
                        summary=f"[{self._subagent_id}] {event.summary or ''}",
                        detail=event.detail,
                    )

            yield SubagentProgressEvent.end(
                request_id=request_id,
                subagent_id=self._subagent_id,
                summary="Completed",
                detail=final_text,
            )

        except Exception as e:
            logger.exception("Child agent '%s' failed", self._subagent_id)
            yield SubagentProgressEvent.error(
                request_id=request_id,
                subagent_id=self._subagent_id,
                error_code=SubagentErrorCode.SUBAGENT_BACKEND_ERROR.value,
                error_message=str(e),
            )


class NoeBuiltinSubagentRuntime(BaseSubagentRuntime):
    """Runtime for built-in specialized agents (browser_use, tacitus).

    Uses a lazy factory to create the underlying agent on first use,
    then streams its output as SubagentProgressEvents.
    """

    def __init__(
        self,
        agent_factory: Any,
        subagent_id: str,
        display_name: str | None = None,
        description: str | None = None,
        task_types: list[str] | None = None,
        supports_hitl: bool = False,
    ) -> None:
        """Initialize with a lazy agent factory.

        Args:
            agent_factory: Zero-arg callable returning the underlying agent.
            subagent_id: Stable identifier for this subagent.
            display_name: Human-readable name.
            description: Capability description.
            task_types: Supported task categories.
            supports_hitl: Whether this agent supports HITL interrupts.
        """
        self._agent_factory = agent_factory
        self._agent_instance: Any = None
        self._subagent_id = subagent_id
        self._descriptor = SubagentDescriptor(
            subagent_id=subagent_id,
            display_name=display_name or subagent_id,
            description=description or f"Built-in subagent: {subagent_id}",
            backend_type=BackendType.BUILTIN,
            task_types=task_types or [],
            supports_streaming=True,
            supports_hitl=supports_hitl,
            cost_hint=CostHint.MEDIUM,
            latency_hint=LatencyHint.BATCH,
        )

    @classmethod
    def get_descriptor(cls) -> SubagentDescriptor:
        raise NotImplementedError("NoeBuiltinSubagentRuntime uses instance-specific descriptors")

    @property
    def descriptor(self) -> SubagentDescriptor:
        return self._descriptor

    async def _ensure_agent(self) -> Any:
        """Lazily instantiate the underlying agent."""
        if self._agent_instance is None:
            result = self._agent_factory()
            if hasattr(result, "__await__"):
                self._agent_instance = await result
            else:
                self._agent_instance = result
        return self._agent_instance

    async def health(self) -> bool:
        return True

    async def execute(
        self,
        task: str,
        **kwargs: Any,
    ) -> AsyncGenerator[SubagentProgressEvent, None]:
        """Execute task via the built-in agent, yielding SubagentProgressEvents."""
        request_id = kwargs.get("request_id", "unknown")

        yield SubagentProgressEvent.start(
            request_id=request_id,
            subagent_id=self._subagent_id,
            summary=f"Starting {self._subagent_id}",
        )

        try:
            agent = await self._ensure_agent()

            if hasattr(agent, "astream_progress"):
                from noesium.core.event import ProgressEventType

                final_text = ""
                async for event in agent.astream_progress(task):
                    etype = event.type
                    if etype == ProgressEventType.FINAL_ANSWER:
                        final_text = event.text or ""
                    elif etype in (
                        ProgressEventType.SESSION_START,
                        ProgressEventType.SESSION_END,
                    ):
                        pass  # suppress session wrapper events from subagent
                    elif etype == ProgressEventType.TOOL_START:
                        # tool_call() already sets summary; pass extra fields via kwargs only
                        yield SubagentProgressEvent.tool_call(
                            request_id=request_id,
                            subagent_id=self._subagent_id,
                            tool_name=event.tool_name or "browser_action",
                            tool_args=event.tool_args or {},
                            payload={"child_event_type": "tool.start", "agent_type": self._subagent_id},
                        )
                    elif etype == ProgressEventType.TOOL_END:
                        # create_tool_result() already sets summary; pass extra fields via kwargs only
                        yield SubagentProgressEvent.create_tool_result(
                            request_id=request_id,
                            subagent_id=self._subagent_id,
                            tool_name=event.tool_name or "browser_action",
                            result=event.tool_result or "",
                            payload={"child_event_type": "tool.end", "agent_type": self._subagent_id},
                        )
                    elif etype == ProgressEventType.PLAN_CREATED:
                        yield SubagentProgressEvent.progress(
                            request_id=request_id,
                            subagent_id=self._subagent_id,
                            summary=event.summary or "Plan created",
                            detail=event.detail,
                            payload={
                                "child_event_type": "plan.created",
                                "agent_type": self._subagent_id,
                                "plan_snapshot": event.plan_snapshot,
                            },
                        )
                    elif etype == ProgressEventType.PLAN_REVISED:
                        yield SubagentProgressEvent.progress(
                            request_id=request_id,
                            subagent_id=self._subagent_id,
                            summary=event.summary or "Plan revised",
                            detail=event.detail,
                            payload={
                                "child_event_type": "plan.revised",
                                "agent_type": self._subagent_id,
                                "plan_snapshot": event.plan_snapshot,
                            },
                        )
                    elif etype == ProgressEventType.STEP_START:
                        yield SubagentProgressEvent.progress(
                            request_id=request_id,
                            subagent_id=self._subagent_id,
                            summary=event.summary or f"Step {(event.step_index or 0) + 1} starting",
                            detail=event.detail,
                            payload={
                                "child_event_type": "step.start",
                                "agent_type": self._subagent_id,
                                "step_index": event.step_index,
                                "step_desc": event.step_desc,
                            },
                        )
                    elif etype == ProgressEventType.STEP_COMPLETE:
                        yield SubagentProgressEvent.progress(
                            request_id=request_id,
                            subagent_id=self._subagent_id,
                            summary=event.summary or f"Step {(event.step_index or 0) + 1} complete",
                            detail=event.detail,
                            payload={
                                "child_event_type": "step.complete",
                                "agent_type": self._subagent_id,
                                "step_index": event.step_index,
                            },
                        )
                    elif etype == ProgressEventType.THINKING:
                        # thought() sets detail=thought; do not pass detail= again via kwargs
                        yield SubagentProgressEvent.thought(
                            request_id=request_id,
                            subagent_id=self._subagent_id,
                            thought=event.summary or "",
                            payload={"agent_type": self._subagent_id},
                        )
                    else:
                        # Generic progress for any remaining event types
                        yield SubagentProgressEvent.progress(
                            request_id=request_id,
                            subagent_id=self._subagent_id,
                            summary=event.summary or "",
                            detail=event.detail,
                            payload={"agent_type": self._subagent_id},
                        )

                yield SubagentProgressEvent.end(
                    request_id=request_id,
                    subagent_id=self._subagent_id,
                    summary="Completed",
                    detail=final_text,
                )

            else:
                # Non-streaming fallback
                if hasattr(agent, "arun"):
                    result = await agent.arun(task)
                elif hasattr(agent, "research"):
                    res = await agent.research(task)
                    result = res.content if hasattr(res, "content") else str(res)
                else:
                    raise RuntimeError(f"Agent {self._subagent_id} has no astream_progress/arun/research method")

                yield SubagentProgressEvent.end(
                    request_id=request_id,
                    subagent_id=self._subagent_id,
                    summary="Completed",
                    detail=str(result),
                )

        except Exception as e:
            logger.exception("Built-in subagent '%s' failed", self._subagent_id)
            yield SubagentProgressEvent.error(
                request_id=request_id,
                subagent_id=self._subagent_id,
                error_code=SubagentErrorCode.SUBAGENT_BACKEND_ERROR.value,
                error_message=str(e),
            )

    async def shutdown(self) -> None:
        """Clean up the underlying agent if needed."""
        if self._agent_instance is not None:
            if hasattr(self._agent_instance, "cleanup"):
                await self._agent_instance.cleanup()
            self._agent_instance = None
        await super().shutdown()


class NoeCliSubagentRuntime(BaseSubagentRuntime):
    """Runtime for external CLI agents via ExternalCliAdapter.

    Supports oneshot execution mode. For daemon (persistent) CLI agents,
    use ExternalCliAdapter directly.
    """

    def __init__(
        self,
        cli_adapter: Any,
        config: Any,
    ) -> None:
        """Initialize with CLI adapter and config.

        Args:
            cli_adapter: ExternalCliAdapter instance.
            config: CliSubagentConfig with name, mode, task_types, etc.
        """
        self._cli_adapter = cli_adapter
        self._config = config
        self._subagent_id = config.name
        self._descriptor = SubagentDescriptor(
            subagent_id=config.name,
            display_name=config.name,
            description=f"CLI subagent: {config.name} (mode={config.mode})",
            backend_type=BackendType.CLI,
            task_types=list(config.task_types) if config.task_types else [],
            supports_streaming=False,
            cost_hint=CostHint.VARIABLE,
            latency_hint=LatencyHint.SLOW,
        )

    @classmethod
    def get_descriptor(cls) -> SubagentDescriptor:
        raise NotImplementedError("NoeCliSubagentRuntime uses instance-specific descriptors")

    @property
    def descriptor(self) -> SubagentDescriptor:
        return self._descriptor

    async def health(self) -> bool:
        return True

    async def execute(
        self,
        task: str,
        **kwargs: Any,
    ) -> AsyncGenerator[SubagentProgressEvent, None]:
        """Execute task via CLI oneshot, yielding SubagentProgressEvents."""
        request_id = kwargs.get("request_id", "unknown")

        yield SubagentProgressEvent.start(
            request_id=request_id,
            subagent_id=self._subagent_id,
            summary=f"Starting CLI: {self._subagent_id}",
        )

        try:
            result = await self._cli_adapter.execute_oneshot(
                self._subagent_id,
                task,
                **{k: v for k, v in kwargs.items() if k != "request_id"},
            )

            # Handle CliExecutionResult object or plain string
            if hasattr(result, "success"):
                if not result.success:
                    yield SubagentProgressEvent.error(
                        request_id=request_id,
                        subagent_id=self._subagent_id,
                        error_code=SubagentErrorCode.SUBAGENT_BACKEND_ERROR.value,
                        error_message=result.error or "CLI execution failed",
                    )
                    return
                output = result.content or ""
            else:
                output = str(result)

            yield SubagentProgressEvent.end(
                request_id=request_id,
                subagent_id=self._subagent_id,
                summary="CLI completed",
                detail=output,
            )

        except Exception as e:
            logger.exception("CLI subagent '%s' failed", self._subagent_id)
            yield SubagentProgressEvent.error(
                request_id=request_id,
                subagent_id=self._subagent_id,
                error_code=SubagentErrorCode.SUBAGENT_BACKEND_ERROR.value,
                error_message=str(e),
            )

    async def shutdown(self) -> None:
        """Terminate CLI daemon process if applicable."""
        if self._config.mode == "daemon" and hasattr(self._cli_adapter, "terminate"):
            try:
                await self._cli_adapter.terminate(self._subagent_id)
            except Exception as e:
                logger.warning("Failed to terminate CLI subagent '%s': %s", self._subagent_id, e)
        await super().shutdown()
