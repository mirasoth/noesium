"""Noe configuration (impl guide §3.1, §7)."""

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


class NoeMode(str, Enum):
    ASK = "ask"
    AGENT = "agent"


class NoeConfig(BaseModel):
    """Configuration for Noe.

    In ask mode the following are forced:
      max_iterations=1, enabled_toolkits=[], permissions=[], persist_memory=False
    """

    mode: NoeMode = NoeMode.AGENT
    llm_provider: str = Field(default_factory=lambda: os.getenv("NOESIUM_LLM_PROVIDER", "openai"))
    planning_model: str | None = None

    max_iterations: int = 25
    max_tool_calls_per_step: int = 5
    reflection_interval: int = 3
    interface_mode: str = "library"  # library | tui

    # Progress reporting (impl guide §5.5, §5.9)
    progress_callbacks: list[Callable] = Field(default_factory=list)
    session_log_dir: str = ".noe_sessions"
    enable_session_logging: bool = True

    enabled_toolkits: list[str] = Field(
        default_factory=lambda: [
            "wizsearch",
            "jina_research",
            "bash",
            "python_executor",
            "file_edit",
            "memory",
            "document",
            "image",
            "tabular_data",
            "video",
            "user_interaction",
        ],
    )
    mcp_servers: list[dict[str, Any]] = Field(default_factory=list)
    custom_tools: list[Callable] = Field(default_factory=list)

    memory_providers: list[str] = Field(
        default_factory=lambda: ["working", "event_sourced", "memu"],
    )
    memu_memory_dir: str = ".noe_memory"
    memu_user_id: str = "default_user"
    persist_memory: bool = True

    working_directory: str | None = None
    permissions: list[str] = Field(
        default_factory=lambda: [
            "fs:read",
            "fs:write",
            "net:outbound",
            "shell:execute",
        ],
    )
    enable_subagents: bool = True
    subagent_max_depth: int = 2

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
