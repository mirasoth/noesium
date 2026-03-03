"""Capability provider adapters for tools, MCP tools, skills, and agents (RFC-0005).

Each adapter wraps an existing Noesium construct into the unified
``CapabilityProvider`` protocol so it can be registered in the
``CapabilityRegistry``.
"""

from __future__ import annotations

import logging
from typing import Any

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
    """Wraps an in-process NoeAgent child as a capability provider (stateful).

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

    Health check delegates to the adapter's process-level liveness check.
    """

    def __init__(
        self,
        name: str,
        adapter: Any,
        *,
        task_types: list[str] | None = None,
    ) -> None:
        self._name = name
        self._adapter = adapter
        self._descriptor = CapabilityDescriptor(
            capability_id=f"cli_agent:{name}",
            version="1.0.0",
            capability_type=CapabilityType.CLI_AGENT,
            description=f"External CLI subagent: {name}",
            determinism=DeterminismClass.STOCHASTIC,
            side_effects=SideEffectClass.EFFECTFUL,
            latency=LatencyClass.BATCH,
            tags=["cli_subagent", f"cli:{name}"] + (task_types or []),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    async def invoke(self, **kwargs: Any) -> Any:
        message = kwargs.get("message", kwargs.get("task", str(kwargs)))
        return await self._adapter.interact(self._name, message)

    async def health(self) -> bool:
        return await self._adapter.health_check(self._name)
