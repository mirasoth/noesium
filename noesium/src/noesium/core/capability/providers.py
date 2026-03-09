"""Capability provider adapters for tools, MCP tools, skills, and agents (RFC-0005).

Each adapter wraps an existing Noesium construct into the unified
``CapabilityProvider`` protocol so it can be registered in the
``CapabilityRegistry``.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

from noesium.core.toolify.atomic import AtomicTool, ToolContext
from noesium.core.toolify.executor import ToolExecutor

from .models import (
    CapabilityDescriptor,
    CapabilityType,
    DeterminismClass,
    LatencyClass,
    SideEffectClass,
)

logger = logging.getLogger(__name__)

_DETERMINISM_MAP: dict[str, DeterminismClass] = {
    "deterministic": DeterminismClass.DETERMINISTIC,
    "stochastic": DeterminismClass.STOCHASTIC,
    "external": DeterminismClass.EXTERNAL,
}
_SIDE_EFFECT_MAP: dict[str, SideEffectClass] = {
    "pure": SideEffectClass.PURE,
    "idempotent": SideEffectClass.IDEMPOTENT,
    "effectful": SideEffectClass.EFFECTFUL,
}


class ToolCapabilityProvider:
    """Wraps an ``AtomicTool`` as a capability provider (stateless, direct invocation)."""

    def __init__(
        self,
        tool: AtomicTool,
        executor: ToolExecutor,
        context: ToolContext,
    ) -> None:
        self._tool = tool
        self._executor = executor
        self._context = context
        self._descriptor = CapabilityDescriptor(
            capability_id=tool.name,
            version="1.0.0",
            capability_type=CapabilityType.TOOL,
            description=tool.description,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema or {},
            determinism=_DETERMINISM_MAP.get(tool.determinism_class, DeterminismClass.STOCHASTIC),
            side_effects=_SIDE_EFFECT_MAP.get(tool.side_effect_class, SideEffectClass.EFFECTFUL),
            latency=LatencyClass.FAST,
            tags=list(tool.tags),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    @property
    def tool(self) -> AtomicTool:
        return self._tool

    async def invoke(self, **kwargs: Any) -> Any:
        return await self._executor.run(self._tool, self._context, **kwargs)

    async def health(self) -> bool:
        return True


class MCPCapabilityProvider:
    """Wraps an MCP session tool as a capability provider (stateless, remote)."""

    def __init__(
        self,
        tool: AtomicTool,
        executor: ToolExecutor,
        context: ToolContext,
    ) -> None:
        self._tool = tool
        self._executor = executor
        self._context = context
        self._descriptor = CapabilityDescriptor(
            capability_id=tool.name,
            version="1.0.0",
            capability_type=CapabilityType.MCP_TOOL,
            description=tool.description,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema or {},
            determinism=DeterminismClass.EXTERNAL,
            side_effects=SideEffectClass.EFFECTFUL,
            latency=LatencyClass.FAST,
            tags=list(tool.tags),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    @property
    def tool(self) -> AtomicTool:
        return self._tool

    async def invoke(self, **kwargs: Any) -> Any:
        return await self._executor.run(self._tool, self._context, **kwargs)

    async def health(self) -> bool:
        return True


class SkillCapabilityProvider:
    """Wraps a ``Skill`` composite as a capability provider."""

    def __init__(
        self,
        skill: Any,
        tool_registry: Any,
        tool_executor: Any,
        context: Any,
    ) -> None:
        self._skill = skill
        self._tool_registry = tool_registry
        self._tool_executor = tool_executor
        self._context = context
        self._descriptor = CapabilityDescriptor(
            capability_id=skill.name,
            version="1.0.0",
            capability_type=CapabilityType.SKILL,
            description=skill.description,
            input_schema=skill.input_schema,
            output_schema=skill.output_schema or {},
            determinism=DeterminismClass.STOCHASTIC,
            side_effects=SideEffectClass.EFFECTFUL,
            latency=LatencyClass.FAST,
            tags=list(getattr(skill, "tags", [])),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    async def invoke(self, **kwargs: Any) -> Any:
        return await self._skill.execute(
            tool_registry=self._tool_registry,
            tool_executor=self._tool_executor,
            context=self._context,
            **kwargs,
        )

    async def health(self) -> bool:
        return True


class AgentCapabilityProvider:
    """Wraps an in-process child agent as a capability provider (stateful).

    The agent is lazily spawned on first invocation if ``spawn_fn`` is provided,
    or it wraps an already-running child agent instance.
    """

    def __init__(
        self,
        name: str,
        agent: Any,
        *,
        task_types: list[str] | None = None,
    ) -> None:
        self._name = name
        self._agent = agent
        self._descriptor = CapabilityDescriptor(
            capability_id=f"agent:{name}",
            version="1.0.0",
            capability_type=CapabilityType.AGENT,
            description=f"In-process subagent: {name}",
            determinism=DeterminismClass.STOCHASTIC,
            side_effects=SideEffectClass.EFFECTFUL,
            latency=LatencyClass.BATCH,
            tags=["subagent", f"agent:{name}"] + (task_types or []),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    @property
    def agent(self) -> Any:
        return self._agent

    async def invoke(self, **kwargs: Any) -> Any:
        message = kwargs.get("message", kwargs.get("task", str(kwargs)))
        return await self._agent.arun(message)

    async def health(self) -> bool:
        return self._agent is not None


class CliAgentCapabilityProvider:
    """Wraps an ``ExternalCliAdapter`` handle as a capability provider (stateful).

    Supports both execution modes:
    - oneshot: Each invocation spawns a new process (recommended for CLI tools like Claude)
    - daemon: Interacts with a persistent daemon process

    Health check delegates to the adapter's process-level liveness check for daemons,
    or config registration check for oneshot mode.
    """

    def __init__(
        self,
        name: str,
        adapter: Any,
        *,
        task_types: list[str] | None = None,
        mode: str = "oneshot",
    ) -> None:
        self._name = name
        self._adapter = adapter
        self._mode = mode
        self._descriptor = CapabilityDescriptor(
            capability_id=f"cli_agent:{name}",
            version="1.0.0",
            capability_type=CapabilityType.CLI_AGENT,
            description=f"External CLI subagent: {name} (mode={mode})",
            determinism=DeterminismClass.STOCHASTIC,
            side_effects=SideEffectClass.EFFECTFUL,
            latency=LatencyClass.BATCH,
            tags=["cli_subagent", f"cli:{name}", f"mode:{mode}"] + (task_types or []),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    @property
    def mode(self) -> str:
        return self._mode

    async def invoke(self, **kwargs: Any) -> Any:
        """Invoke the CLI subagent.

        For oneshot mode, spawns a new process and captures output.
        For daemon mode, sends message to existing persistent process.
        """
        message = kwargs.get("message", kwargs.get("task", str(kwargs)))

        # Check adapter's execute_oneshot method (preferred)
        if hasattr(self._adapter, "execute_oneshot"):
            result = await self._adapter.execute_oneshot(
                self._name,
                message,
                **{k: v for k, v in kwargs.items() if k not in ("message", "task")},
            )
            # Handle CliExecutionResult
            if hasattr(result, "success"):
                if result.success:
                    return result.content
                else:
                    return f"Error: {result.error}"
            return result

        # Fallback to interact method (daemon mode)
        return await self._adapter.interact(self._name, message)

    async def health(self) -> bool:
        return await self._adapter.health_check(self._name)


class BuiltInAgentCapabilityProvider:
    """Wraps a built-in subagent (BrowserUseAgent, TacitusAgent) as a capability provider.

    This provider lazily instantiates the agent on first invocation and caches it
    for subsequent calls. Built-in agents run in-process and share the parent's
    LLM client infrastructure.
    """

    def __init__(
        self,
        name: str,
        agent_factory: Any,
        *,
        agent_type: str = "builtin",
        description: str = "",
        task_types: list[str] | None = None,
    ) -> None:
        self._name = name
        self._agent_factory = agent_factory
        self._agent_type = agent_type
        self._agent_instance: Any = None
        self._descriptor = CapabilityDescriptor(
            capability_id=f"builtin_agent:{name}",
            version="1.0.0",
            capability_type=CapabilityType.AGENT,
            description=description or f"Built-in subagent: {name}",
            determinism=DeterminismClass.STOCHASTIC,
            side_effects=SideEffectClass.EFFECTFUL,
            latency=LatencyClass.BATCH,
            tags=["builtin_subagent", f"agent:{name}", agent_type] + (task_types or []),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    @property
    def agent(self) -> Any:
        return self._agent_instance

    async def invoke(self, **kwargs: Any) -> Any:
        """Invoke the built-in agent with the given task.

        The agent is lazily created on first invocation.
        """
        if self._agent_instance is None:
            try:
                factory_result = self._agent_factory()
                # Handle both sync and async factories
                if hasattr(factory_result, "__await__"):
                    self._agent_instance = await factory_result
                else:
                    self._agent_instance = factory_result
            except Exception as exc:
                logger.error("Failed to create built-in agent '%s': %s", self._name, exc)
                raise RuntimeError(f"Failed to create built-in agent '{self._name}': {exc}") from exc

        message = kwargs.get("message", kwargs.get("task", str(kwargs)))

        # Try different invocation patterns
        try:
            if hasattr(self._agent_instance, "arun"):
                result = await self._agent_instance.arun(message)
            elif hasattr(self._agent_instance, "research"):
                # TacitusAgent uses research() method
                result = await self._agent_instance.research(message)
                # ResearchOutput has a content attribute
                if hasattr(result, "content"):
                    result = result.content
            elif hasattr(self._agent_instance, "run"):
                # Check if run is async
                import inspect

                if inspect.iscoroutinefunction(self._agent_instance.run):
                    result = await self._agent_instance.run(message)
                else:
                    result = self._agent_instance.run(message)
            else:
                raise RuntimeError(f"Agent '{self._name}' has no run/arun/research method")
            return result
        except Exception as exc:
            logger.error("Built-in agent '%s' invocation failed: %s", self._name, exc)
            raise

    async def health(self) -> bool:
        """Built-in agents are always healthy (in-process)."""
        return True

    async def invoke_streaming(
        self,
        message: str,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        """Invoke the built-in agent with progress streaming.

        This method streams ProgressEvent objects wrapped as SUBAGENT_PROGRESS
        events, allowing real-time visibility into agent execution.

        Args:
            message: The task message for the agent.
            **kwargs: Additional arguments passed to the agent.

        Yields:
            ProgressEvent: Events wrapped with subagent context.
        """
        from noesium.core.event import ProgressEvent, ProgressEventType

        # Ensure agent is created
        if self._agent_instance is None:
            try:
                factory_result = self._agent_factory()
                if hasattr(factory_result, "__await__"):
                    self._agent_instance = await factory_result
                else:
                    self._agent_instance = factory_result
            except Exception as exc:
                logger.error("Failed to create built-in agent '%s': %s", self._name, exc)
                yield ProgressEvent(
                    type=ProgressEventType.ERROR,
                    subagent_id=self._name,
                    error=str(exc),
                    summary=f"Failed to create agent: {exc}",
                )
                raise RuntimeError(f"Failed to create built-in agent '{self._name}': {exc}") from exc

        # Check for astream_progress support
        if hasattr(self._agent_instance, "astream_progress"):
            final_result = ""
            async for event in self._agent_instance.astream_progress(message, **kwargs):
                # Skip SESSION_START/SESSION_END for wrapped events
                if event.type in (
                    ProgressEventType.SESSION_START,
                    ProgressEventType.SESSION_END,
                ):
                    continue

                # Wrap as SUBAGENT_PROGRESS
                wrapped = ProgressEvent(
                    type=ProgressEventType.SUBAGENT_PROGRESS,
                    session_id=event.session_id,
                    sequence=event.sequence,
                    subagent_id=self._name,
                    summary=f"[{self._name}] {event.summary or ''}",
                    detail=event.detail,
                    tool_name=event.tool_name,
                    tool_result=event.tool_result,
                    step_index=event.step_index,
                    step_desc=event.step_desc,
                    plan_snapshot=event.plan_snapshot,
                    error=event.error,
                    metadata={
                        "child_event_type": event.type.value,
                        "agent_type": self._agent_type,
                        **(event.metadata or {}),
                    },
                )
                yield wrapped

                # Track final result
                if event.type == ProgressEventType.FINAL_ANSWER:
                    final_result = event.text or ""

            # Emit SUBAGENT_END
            yield ProgressEvent(
                type=ProgressEventType.SUBAGENT_END,
                subagent_id=self._name,
                summary=f"[{self._name}] completed",
                detail=final_result[:500] if final_result else None,
            )
        else:
            # Fallback: emit start/end only (non-streaming agent)
            yield ProgressEvent(
                type=ProgressEventType.SUBAGENT_START,
                subagent_id=self._name,
                summary=f"[{self._name}] started (no streaming support)",
            )

            try:
                result = await self.invoke(message=message, **kwargs)
                result_str = str(result)[:500]
            except Exception as exc:
                result_str = f"Error: {exc}"

            yield ProgressEvent(
                type=ProgressEventType.SUBAGENT_END,
                subagent_id=self._name,
                summary=f"[{self._name}] completed",
                detail=result_str,
            )
