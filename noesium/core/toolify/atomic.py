"""AtomicTool model and supporting types (RFC-2004 §4)."""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from uuid_extensions import uuid7str

from noesium.core.event.envelope import TraceContext
from noesium.core.exceptions import ToolExecutionError


class ToolSource(str, Enum):
    BUILTIN = "builtin"
    LANGCHAIN = "langchain"
    MCP = "mcp"
    USER = "user"


class ToolPermission(str, Enum):
    FS_READ = "fs:read"
    FS_WRITE = "fs:write"
    NET_OUTBOUND = "net:outbound"
    SHELL_EXECUTE = "shell:execute"
    ENV_READ = "env:read"
    MCP_CONNECT = "mcp:connect"


class AtomicTool(BaseModel):
    """The smallest executable unit in the tool system (RFC-2003 §6)."""

    tool_id: str = Field(default_factory=lambda: uuid7str())
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    source: ToolSource = ToolSource.USER
    determinism_class: str = "stochastic"
    side_effect_class: str = "effectful"
    permissions: list[ToolPermission] = Field(default_factory=list)
    timeout_ms: int = 30_000
    tags: list[str] = Field(default_factory=list)
    toolkit_name: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _callable: Callable | None = PrivateAttr(default=None)

    def bind(self, fn: Callable) -> AtomicTool:
        self._callable = fn
        return self

    async def execute(self, **kwargs: Any) -> Any:
        if self._callable is None:
            raise ToolExecutionError(f"Tool {self.name} has no bound callable")
        if asyncio.iscoroutinefunction(self._callable):
            return await self._callable(**kwargs)
        return self._callable(**kwargs)


class ToolContext(BaseModel):
    """Execution context passed to ToolExecutor for each invocation."""

    agent_id: str
    trace: TraceContext = Field(default_factory=TraceContext)
    granted_permissions: list[ToolPermission] = Field(default_factory=list)
    working_directory: str | None = None
    timeout_ms: int = 30_000
