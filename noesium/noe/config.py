"""Noe configuration (impl guide §3.1, §7)."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

_NOE_HOME = Path.home() / ".noe_agent"


class NoeMode(str, Enum):
    ASK = "ask"
    AGENT = "agent"


class CliSubagentConfig(BaseModel):
    """Configuration for an external CLI subagent daemon (impl guide §5.10)."""

    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    timeout: int = 300
    restart_policy: str = "on-failure"
    task_types: list[str] = Field(default_factory=list)


class NoeConfig(BaseModel):
    """Configuration for Noe.

    In ask mode the following are forced:
      max_iterations=1, enabled_toolkits=[], permissions=[], persist_memory=False
    """

    mode: NoeMode = NoeMode.AGENT
    llm_provider: str = Field(default_factory=lambda: os.getenv("NOESIUM_LLM_PROVIDER", "openai"))
    model_name: str | None = None
    planning_model: str | None = None

    max_iterations: int = 25
    max_tool_calls_per_step: int = 5
    reflection_interval: int = 3
    interface_mode: str = "library"

    progress_callbacks: list[Callable] = Field(default_factory=list)
    session_log_dir: str = Field(default_factory=lambda: str(_NOE_HOME / "sessions"))
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
            "arxiv",
            "serper",
            "wikipedia",
            "github",
            "gmail",
            "audio",
            "audio_aliyun",
        ],
    )
    mcp_servers: list[dict[str, Any]] = Field(default_factory=list)
    custom_tools: list[Callable] = Field(default_factory=list)

    memory_providers: list[str] = Field(
        default_factory=lambda: ["working", "event_sourced", "memu"],
    )
    memu_memory_dir: str = Field(default_factory=lambda: str(_NOE_HOME / "memory"))
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
    cli_subagents: list[CliSubagentConfig] = Field(default_factory=list)

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
