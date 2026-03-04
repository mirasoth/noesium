"""Noe configuration (impl guide §3.1, §7)."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel, ConfigDict, Field
from uuid_extensions import uuid7str

_NOE_HOME = Path.home() / ".noeagent"
_NOE_AGENT_CONSOLE_LOG_LEVEL = "ERROR"


class NoeMode(str, Enum):
    ASK = "ask"
    AGENT = "agent"


class AgentSubagentConfig(BaseModel):
    """Configuration for a built-in agent subagent."""

    name: str
    agent_type: str  # browser_use, tacitus, askura
    description: str | None = None
    enabled: bool = True
    # Enhanced capability descriptors for intelligent routing
    task_types: list[str] = Field(
        default_factory=list,
        description="Types of tasks this subagent handles (e.g., ['web_browsing', 'form_filling', 'scraping'])",
    )
    use_cases: list[str] = Field(
        default_factory=list,
        description="Example use cases for semantic matching (e.g., ['Find stock prices', 'Book a flight'])",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Keywords for routing decisions (e.g., ['browser', 'click', 'navigate', 'stock', 'price'])",
    )
    preferred_for: list[str] = Field(
        default_factory=list,
        description="Query patterns this subagent is preferred for (e.g., ['real-time data', 'interactive web'])",
    )
    config: dict[str, Any] | None = Field(
        default=None,
        description="Agent-type-specific options (e.g. browser_use: headless)",
    )


class CliSubagentConfig(BaseModel):
    """Configuration for an external CLI subagent (impl guide §5.10).

    Supports two execution modes:
    - daemon: Long-lived persistent process with bidirectional JSON streaming
    - oneshot: Single execution per request, process exits after completion

    Attributes:
        name: Subagent identifier
        command: Executable command
        args: Command arguments
        env: Environment variables
        timeout: Timeout in seconds
        restart_policy: Restart behavior (daemon mode only)
        task_types: Supported task types
        mode: Execution mode - 'daemon' or 'oneshot'
        output_format: Expected output format from the CLI
        input_format: Input format to send to the CLI (oneshot mode)
        allowed_tools: Tools to allow in the CLI session
        skip_permissions: Skip permission prompts (automation mode)
    """

    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    timeout: int = 300
    restart_policy: str = "on-failure"
    task_types: list[str] = Field(default_factory=list)
    mode: str = "oneshot"  # "daemon" or "oneshot"
    output_format: str = "text"  # "text", "json", "stream-json", "ndjson"
    input_format: str = "text"  # "text", "stream-json"
    allowed_tools: list[str] = Field(default_factory=list)
    skip_permissions: bool = True  # For automation workflows


# Default agent subagents (browser_use and tacitus)
DEFAULT_AGENT_SUBAGENTS = [
    AgentSubagentConfig(
        name="browser_use",
        agent_type="browser_use",
        description="Web automation agent for browser interaction, form filling, and real-time web data extraction",
        enabled=True,
        task_types=["web_browsing", "form_filling", "web_scraping", "dom_interaction", "screenshot"],
        use_cases=[
            "Find real-time stock prices from financial websites",
            "Book flights or hotels on travel sites",
            "Fill out web forms automatically",
            "Navigate multi-page websites",
            "Extract data from interactive web applications",
            "Take screenshots of web pages",
        ],
        keywords=["browser", "click", "navigate", "form", "button", "website", "real-time", "stock price", "booking"],
        preferred_for=["real-time data", "interactive websites", "form submission", "multi-step web workflows"],
    ),
    AgentSubagentConfig(
        name="tacitus",
        agent_type="tacitus",
        description="Research agent with iterative query generation, multi-source web search, and answer synthesis",
        enabled=True,
        task_types=["web_research", "information_synthesis", "multi_source_search", "fact_checking"],
        use_cases=[
            "Research a topic from multiple sources",
            "Find and synthesize information from the web",
            "Answer complex questions requiring multiple searches",
            "Verify facts across different sources",
            "Generate comprehensive research reports",
        ],
        keywords=["research", "search", "synthesize", "information", "multiple sources", "analyze", "compare"],
        preferred_for=["information gathering", "multi-source research", "complex questions", "fact verification"],
    ),
]


def _tui_field(global_config: Any, key: str, default: Any) -> Any:
    """Read a TUI config field from the global config (extra='allow' dict)."""
    tui = getattr(global_config, "tui", None)
    if tui is None:
        return default
    if isinstance(tui, dict):
        return tui.get(key, default)
    return getattr(tui, key, default)


class NoeConfig(BaseModel):
    """Configuration for Noe.

    In ask mode the following are forced:
      max_iterations=1, enabled_toolkits=[], permissions=[], persist_memory=False

    Configuration loading priority (highest to lowest):
      1. Environment variables
      2. Config file (~/.noeagent/config.json)
      3. Default values in code
    """

    mode: NoeMode = NoeMode.AGENT
    llm_provider: str = Field(default_factory=lambda: os.getenv("NOE_LLM_PROVIDER", "openai"))
    model_name: str | None = None
    planning_model: str | None = None

    max_iterations: int = 25
    max_tool_calls_per_step: int = 5
    reflection_interval: int = 3
    interface_mode: str = "library"

    # dotenv loading
    load_dotenv: bool = True
    dotenv_path: str | None = None  # None means auto-detect .env in current directory

    progress_callbacks: list[Callable] = Field(default_factory=list)
    session_log_dir: str = Field(default_factory=lambda: str(_NOE_HOME / "sessions"))
    enable_session_logging: bool = True

    # Session isolation — all per-session artefacts live under session_dir
    session_id: str = Field(default_factory=uuid7str)
    session_dir: str | None = None  # Derived from session_id when None

    # File-based logging level (console is always WARNING for UX simplicity).
    # This is global, affecting noeagent, core, all subagents, and tools.
    file_log_level: str = "INFO"

    # TUI settings
    tui_history_file: str = Field(default_factory=lambda: str(_NOE_HOME / "history.json"))
    tui_history_size: int = 1000

    enabled_toolkits: list[str] = Field(
        default_factory=lambda: [
            "bash",
            "file_edit",
            "document",
            "image",
            "python_executor",
            "tabular_data",
            "wizsearch",
            "user_interaction",
        ],
    )
    toolkit_configs: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Toolkit-specific configuration overrides. Keys are toolkit names, values are config dicts.",
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
    # Built-in agent subagents (browser_use, tacitus, etc.) - in-process agents
    builtin: list[AgentSubagentConfig] = Field(
        default_factory=lambda: [AgentSubagentConfig(**s.model_dump()) for s in DEFAULT_AGENT_SUBAGENTS]
    )
    external: list[CliSubagentConfig] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def effective(self) -> NoeConfig:
        """Return config with ask-mode overrides applied."""
        cfg = self
        if cfg.mode == NoeMode.ASK:
            cfg = cfg.model_copy(
                update={
                    "max_iterations": 1,
                    "enabled_toolkits": [],
                    "permissions": [],
                    "persist_memory": False,
                }
            )
        # Resolve session_dir from session_id when not explicitly set
        if cfg.session_dir is None:
            cfg = cfg.model_copy(update={"session_dir": str(Path(cfg.session_log_dir) / cfg.session_id)})
        return cfg

    def load_dotenv_if_enabled(self) -> None:
        """Load .env file if enabled."""
        if not self.load_dotenv:
            return
        try:
            from dotenv import load_dotenv

            dotenv_path = self.dotenv_path
            if dotenv_path:
                load_dotenv(dotenv_path, override=True)
            else:
                # Auto-detect .env in current directory
                load_dotenv(override=True)
        except ImportError:
            pass

    def get_builtin_subagent(self, name: str) -> Optional[dict]:
        """Get built-in subagent configuration by name.

        Args:
            name: Name of the built-in subagent to retrieve

        Returns:
            Subagent configuration dict or None if not found
        """
        for subagent in self.builtin:
            if subagent.name == name:
                return subagent.model_dump()
        return None

    def get_enabled_builtin_subagents(self) -> list[AgentSubagentConfig]:
        """Get list of enabled built-in subagents."""
        return [s for s in self.builtin if s.enabled]

    @classmethod
    def from_global_config(cls) -> "NoeConfig":
        """Load NoeConfig from global configuration.

        This method loads the centralized configuration from ~/.noeagent/config.json
        and creates a NoeConfig instance from it.

        Returns:
            NoeConfig instance populated from global configuration
        """
        from noesium.core.config import load_config

        global_config = load_config()

        # Get the chat model for the configured provider
        provider_config = global_config.llm.providers.get(global_config.llm.provider, {})
        model_name = (
            provider_config.chat_model if hasattr(provider_config, "chat_model") else provider_config.get("chat_model")
        )

        # Get planning model
        planning_model = global_config.agent.planning_model

        return cls(
            mode=NoeMode(global_config.agent.mode),
            llm_provider=global_config.llm.provider,
            model_name=model_name,
            planning_model=planning_model,
            max_iterations=global_config.agent.max_iterations,
            max_tool_calls_per_step=global_config.agent.max_tool_calls_per_step,
            reflection_interval=global_config.agent.reflection_interval,
            interface_mode="library",
            load_dotenv=getattr(global_config.agent, "load_dotenv", True),
            dotenv_path=getattr(global_config.agent, "dotenv_path", None),
            session_log_dir=global_config.memory.session_log_dir,
            enable_session_logging=global_config.memory.session_logging,
            file_log_level=global_config.logging.file_level or global_config.logging.level,
            tui_history_file=_tui_field(global_config, "history_file", str(_NOE_HOME / "history.json")),
            tui_history_size=_tui_field(global_config, "history_size", 1000),
            enabled_toolkits=global_config.tools.enabled_toolkits,
            toolkit_configs={
                name: entry.model_dump(exclude_none=True, exclude={"timeout", "shell", "max_output_length"})
                for name, entry in global_config.tools.toolkit_configs.items()
            },
            mcp_servers=[s.model_dump() for s in global_config.tools.mcp_servers],
            memory_providers=global_config.memory.providers,
            memu_memory_dir=global_config.memory.memu.memory_dir,
            memu_user_id=global_config.memory.memu.user_id,
            persist_memory=global_config.memory.persist,
            working_directory=global_config.working_directory,
            permissions=global_config.tools.permissions,
            enable_subagents=global_config.subagents.enabled,
            subagent_max_depth=global_config.subagents.max_depth,
            builtin=[
                AgentSubagentConfig(
                    name=s.name,
                    agent_type=s.agent_type,
                    description=s.description,
                    enabled=getattr(s, "enabled", True),
                    config=getattr(s, "config", None),
                )
                for s in global_config.subagents.builtin
            ]
            or [AgentSubagentConfig(**s.model_dump()) for s in DEFAULT_AGENT_SUBAGENTS],
            external=[CliSubagentConfig(**s.model_dump()) for s in global_config.subagents.external],
        )
