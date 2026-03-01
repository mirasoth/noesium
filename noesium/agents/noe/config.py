"""Noet configuration (impl guide §4.1)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


class NoeMode(str, Enum):
    ASK = "ask"
    AGENT = "agent"


class NoeConfig(BaseModel):
    """Configuration for Noet.

    In ask mode the following are forced:
      max_iterations=1, enabled_toolkits=[], permissions=[], persist_memory=False
    """

    mode: NoeMode = NoeMode.AGENT
    llm_provider: str = "openrouter"
    model_name: str | None = None
    planning_model: str | None = None

    max_iterations: int = 25
    max_tool_calls_per_step: int = 5
    reflection_interval: int = 3

    enabled_toolkits: list[str] = Field(
        default_factory=lambda: ["search", "bash", "python_executor", "file_edit"],
    )
    mcp_servers: list[dict[str, Any]] = Field(default_factory=list)
    custom_tools: list[Callable] = Field(default_factory=list)

    memory_providers: list[str] = Field(
        default_factory=lambda: ["working", "event_sourced"],
    )
    persist_memory: bool = True

    working_directory: str | None = None
    permissions: list[str] = Field(
        default_factory=lambda: ["fs:read", "fs:write", "net:outbound", "shell:execute"],
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def effective(self) -> NoeConfig:
        """Return config with ask-mode overrides applied."""
        if self.mode == NoeMode.ASK:
            return self.model_copy(
                update={
                    "max_iterations": 1,
                    "enabled_toolkits": [],
                    "permissions": [],
                    "persist_memory": False,
                }
            )
        return self
