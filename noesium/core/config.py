"""Noesium Core Configuration System (RFC-1007: framework layer, no application names).

Configuration values are loaded with the following precedence (highest to lowest):

1. Environment Variables - Always take highest precedence
2. Config File - Path from NOESIUM_CONFIG or NOESIUM_HOME/config.json
3. Default Values - Hard-coded defaults in code

Usage:
    from noesium.core.config import load_config

    config = load_config()
    print(f"LLM Provider: {config.llm.provider}")
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from noesium.core.consts import (
    CONFIG_VERSION,
    DEFAULT_CONFIG_PATH,
    NOESIUM_HOME,
)

# =============================================================================
# Configuration Models
# =============================================================================


class LLMProviderConfig(BaseModel):
    """Configuration for a single LLM provider.

    Attributes:
        api_key: API key for the provider (can also use env var)
        base_url: Custom base URL for the provider
        chat_model: Model for chat completion
        vision_model: Model for vision tasks
        embed_model: Model for embeddings
        structured_output: Enable structured output
        model_path: Path to model file (for local providers like LlamaCPP)
    """

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    chat_model: Optional[str] = None
    vision_model: Optional[str] = None
    embed_model: Optional[str] = None
    structured_output: bool = True
    model_path: Optional[str] = None  # For LlamaCPP


class LLMConfig(BaseModel):
    """LLM configuration.

    Attributes:
        provider: Default LLM provider name
        providers: Provider-specific configurations
    """

    provider: str = Field(default_factory=lambda: os.getenv("NOESIUM_LLM_PROVIDER", "openai"))
    providers: Dict[str, LLMProviderConfig] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """Agent behavior configuration.

    Attributes:
        mode: Agent mode - "ask" or "agent"
        max_iterations: Maximum reasoning iterations
        max_tool_calls_per_step: Tool calls per step limit
        reflection_interval: Steps between reflections
        planning_model: Model for planning (defaults to chat model)
        load_dotenv: Load .env file from working directory
        dotenv_path: Custom path to .env file (None for auto-detect)
        verbose: Enable verbose logging (INFO level instead of WARNING)
    """

    mode: str = "agent"  # "ask" or "agent"
    max_iterations: int = 25
    max_tool_calls_per_step: int = 5
    reflection_interval: int = 3
    planning_model: Optional[str] = None
    load_dotenv: bool = True
    dotenv_path: Optional[str] = None
    verbose: bool = False


class MCPServerConfig(BaseModel):
    """MCP server configuration.

    Attributes:
        name: Server identifier
        command: Executable command
        args: Command arguments
        env: Environment variables
    """

    name: str
    command: str
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)


class ToolkitConfigEntry(BaseModel):
    """Toolkit-specific configuration.

    Supports both common toolkit settings and toolkit-specific parameters.
    Toolkit-specific configs are passed directly to the toolkit's config dict.

    Attributes:
        timeout: Timeout in seconds
        shell: Shell to use (for bash toolkit)
        max_output_length: Maximum output length
        **kwargs: Toolkit-specific configuration parameters (e.g., web_search.enabled_engines)
    """

    timeout: Optional[int] = None
    shell: Optional[str] = None
    max_output_length: Optional[int] = None

    class Config:
        extra = "allow"  # Allow toolkit-specific fields


class ToolsConfig(BaseModel):
    """Tools configuration.

    Attributes:
        enabled_toolkits: List of toolkit names to enable
        toolkit_configs: Toolkit-specific configurations
        mcp_servers: MCP server configurations
        permissions: Permission grants
    """

    enabled_toolkits: List[str] = Field(
        default_factory=lambda: [
            "bash",
            "file_edit",
            "document",
            "image",
            "python_executor",
            "tabular_data",
            "web_search",
            "user_interaction",
        ]
    )
    toolkit_configs: Dict[str, ToolkitConfigEntry] = Field(default_factory=dict)
    mcp_servers: List[MCPServerConfig] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=lambda: ["fs:read", "fs:write", "net:outbound", "shell:execute"])


class AgentSubagentConfig(BaseModel):
    """Built-in agent subagent configuration.

    Attributes:
        name: Subagent identifier
        agent_type: Agent type (browser_use, tacitus, askura)
        description: Description of subagent purpose
        config: Optional agent-type-specific options (e.g. browser_use headless)
    """

    name: str
    agent_type: str  # browser_use, tacitus, askura
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class CliSubagentConfig(BaseModel):
    """CLI subagent configuration.

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
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    timeout: int = 300
    restart_policy: str = "on-failure"
    task_types: List[str] = Field(default_factory=list)
    mode: str = "oneshot"  # "daemon" or "oneshot"
    output_format: str = "text"  # "text", "json", "stream-json", "ndjson"
    input_format: str = "text"  # "text", "stream-json"
    allowed_tools: List[str] = Field(default_factory=list)
    skip_permissions: bool = True  # For automation workflows


class SubagentsConfig(BaseModel):
    """Subagents configuration.

    Attributes:
        enabled: Enable subagent spawning
        max_depth: Maximum nesting depth
        builtin: Built-in agent subagent configurations (in-process agents)
        external: External CLI subagent configurations (spawned processes)
    """

    enabled: bool = True
    max_depth: int = 2
    builtin: List[AgentSubagentConfig] = Field(default_factory=list)
    external: List[CliSubagentConfig] = Field(default_factory=list)


class MemuMemoryConfig(BaseModel):
    """Memu memory configuration.

    Attributes:
        memory_dir: Directory for memory storage
        user_id: User identifier
    """

    memory_dir: str = str(NOESIUM_HOME / "memory")
    user_id: str = "default_user"


class EventSourcedMemoryConfig(BaseModel):
    """Event-sourced memory configuration.

    Attributes:
        db_path: Path to SQLite database file
    """

    db_path: str = str(NOESIUM_HOME / "data" / "events.db")


class MemoryConfig(BaseModel):
    """Memory configuration.

    Attributes:
        providers: Enabled memory providers
        persist: Persist memory across sessions
        session_logging: Enable session logging
        session_log_dir: Directory for session logs
        memu: Memu-specific config
        event_sourced: Event-sourced memory config
    """

    providers: List[str] = Field(default_factory=lambda: ["working", "event_sourced", "memu"])
    persist: bool = True
    session_logging: bool = True
    session_log_dir: str = str(NOESIUM_HOME / "sessions")
    memu: MemuMemoryConfig = Field(default_factory=MemuMemoryConfig)
    event_sourced: EventSourcedMemoryConfig = Field(default_factory=EventSourcedMemoryConfig)


class OpikTracingConfig(BaseModel):
    """OPIK tracing configuration.

    Attributes:
        use_local: Use local Opik deployment
        local_url: Local Opik URL
        api_key: API key for Comet ML/Opik cloud
        workspace: Workspace name for cloud
        project_name: Project name for organizing traces
        url: Custom Opik URL for cloud deployment
    """

    use_local: bool = True
    local_url: str = "http://localhost:5173"
    api_key: Optional[str] = None
    workspace: Optional[str] = None
    project_name: str = "noesium-llm"
    url: Optional[str] = None


class TracingConfig(BaseModel):
    """Tracing configuration.

    Attributes:
        enabled: Enable Opik tracing
        provider: Tracing provider (currently only "opik" supported)
        opik: OPIK-specific config
    """

    enabled: bool = Field(default_factory=lambda: os.getenv("NOESIUM_OPIK_TRACING", "false").lower() == "true")
    provider: str = "opik"
    opik: OpikTracingConfig = Field(default_factory=OpikTracingConfig)


class LoggingConfig(BaseModel):
    """Common logging configuration (core layer).

    Both console and file default to the same ``level`` (INFO).
    Application layers may override the console level
    for their own UX needs via ``setup_logging(console_level=...)``.

    Attributes:
        level: Default log level for both console and file.
        file_level: Optional file-only override. When None, falls back to ``level``.
        rotation: Rotation size/time (reserved for future use).
        retention: Retention period (reserved for future use).
    """

    level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    file_level: Optional[str] = Field(default_factory=lambda: os.getenv("NOESIUM_FILE_LOG_LEVEL"))
    rotation: str = "10 MB"
    retention: str = "7 days"


class FrameworkConfig(BaseModel):
    """Top-level configuration model.

    Contains core framework sections (LLM, tools, memory, logging, etc.).
    Application-specific sections (e.g. ``tui``) are accepted via
    ``extra = "allow"`` but not modeled here — they are handled by
    the application layer.

    Attributes:
        version: Configuration schema version
        llm: LLM configuration
        agent: Agent behavior configuration
        tools: Tools configuration
        subagents: Subagents configuration
        memory: Memory configuration
        tracing: Tracing configuration
        logging: Logging configuration
        working_directory: Default working directory
    """

    version: str = CONFIG_VERSION
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    subagents: SubagentsConfig = Field(default_factory=SubagentsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    working_directory: Optional[str] = None

    class Config:
        extra = "allow"  # Allow extra fields for forward compatibility


# =============================================================================
# Configuration Functions
# =============================================================================


def get_config_path() -> Path:
    """Get configuration file path.

    The path is determined in this order:
    1. NOESIUM_CONFIG environment variable
    2. Default: NOESIUM_HOME/config.json (e.g. ~/.noesium/config.json)

    Returns:
        Path to the configuration file
    """
    config_path = os.getenv("NOESIUM_CONFIG")
    if config_path:
        return Path(config_path)
    return DEFAULT_CONFIG_PATH


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-merge override into base. Override values take precedence. Lists and non-dicts replace base."""
    result = dict(base)
    for key, override_value in override.items():
        if key not in result:
            result[key] = override_value
        elif isinstance(override_value, dict) and isinstance(result[key], dict):
            result[key] = _deep_merge(result[key], override_value)
        else:
            result[key] = override_value
    return result


def _normalize_config_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize configuration data to match expected schema.

    This handles common format variations and ensures the data structure
    matches what the Pydantic models expect.

    Args:
        data: Raw configuration data from file

    Returns:
        Normalized configuration data
    """
    # Ensure subagents.builtin is a list
    subagents = data.get("subagents", {})
    if isinstance(subagents.get("builtin"), dict):
        # Convert dict to empty list (old format had nested config here)
        subagents["builtin"] = []

    # Ensure subagents.external is a list
    if isinstance(subagents.get("external"), dict):
        subagents["external"] = []

    # Ensure memory.providers is a list
    memory = data.get("memory", {})
    if isinstance(memory.get("providers"), dict):
        memory["providers"] = list(memory["providers"].keys())

    # Ensure tools.enabled_toolkits is a list
    tools = data.get("tools", {})
    if isinstance(tools.get("enabled_toolkits"), dict):
        tools["enabled_toolkits"] = list(tools["enabled_toolkits"].keys())

    # Ensure tools.permissions is a list
    if isinstance(tools.get("permissions"), dict):
        tools["permissions"] = list(tools["permissions"].keys())

    # Ensure tools.mcp_servers is a list
    if isinstance(tools.get("mcp_servers"), dict):
        tools["mcp_servers"] = []

    # Remove obsolete logging.file (log path is now session-isolated)
    logging_section = data.get("logging", {})
    logging_section.pop("file", None)

    return data


def load_config(config_path: Optional[Path] = None) -> FrameworkConfig:
    """Load configuration from file.

    If the config file doesn't exist, creates a default configuration
    and saves it to the config path. If the file is empty or invalid JSON,
    it is treated as empty config and merged with defaults so that e.g. ``{}``
    yields the same behavior as a full default config.

    Args:
        config_path: Optional path to config file. If not provided,
                    uses get_config_path() to determine the path.

    Returns:
        Loaded FrameworkConfig instance
    """
    if config_path is None:
        config_path = get_config_path()

    # Create default config if file doesn't exist
    if not config_path.exists():
        config = FrameworkConfig()
        save_config(config, config_path)
        return config

    # Load from file; treat empty or invalid content as {}
    raw = config_path.read_text().strip()
    if not raw:
        data = {}
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
        if not isinstance(data, dict):
            data = {}

    # Merge with defaults so empty {} gets full default structure
    default_dict = FrameworkConfig().model_dump()
    data = _deep_merge(default_dict, data)

    # Normalize data to handle format variations
    data = _normalize_config_data(data)

    # Apply environment variable overrides
    data = apply_env_overrides(data)

    return FrameworkConfig(**data)


def save_config(config: FrameworkConfig, config_path: Optional[Path] = None) -> None:
    """Save configuration to file.

    Args:
        config: FrameworkConfig instance to save
        config_path: Optional path to save to. If not provided,
                    uses get_config_path() to determine the path.
    """
    if config_path is None:
        config_path = get_config_path()

    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config
    with open(config_path, "w") as f:
        json.dump(config.model_dump(exclude_none=True), f, indent=2)


def apply_env_overrides(data: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to config data.

    Environment variables take highest precedence over config file values.

    Args:
        data: Configuration data dictionary

    Returns:
        Updated configuration data with environment variable overrides applied
    """
    # Ensure nested structures exist
    data.setdefault("llm", {})
    data["llm"].setdefault("providers", {})

    # LLM Provider
    if provider := os.getenv("NOESIUM_LLM_PROVIDER"):
        data["llm"]["provider"] = provider

    # OpenAI
    openai_config = data["llm"]["providers"].setdefault("openai", {})
    if api_key := os.getenv("OPENAI_API_KEY"):
        openai_config["api_key"] = api_key
    if base_url := os.getenv("OPENAI_BASE_URL"):
        openai_config["base_url"] = base_url
    if model := os.getenv("OPENAI_CHAT_MODEL"):
        openai_config["chat_model"] = model
    if model := os.getenv("OPENAI_VISION_MODEL"):
        openai_config["vision_model"] = model
    if model := os.getenv("OPENAI_EMBED_MODEL"):
        openai_config["embed_model"] = model

    # OpenRouter
    openrouter_config = data["llm"]["providers"].setdefault("openrouter", {})
    if api_key := os.getenv("OPENROUTER_API_KEY"):
        openrouter_config["api_key"] = api_key
    if base_url := os.getenv("OPENROUTER_BASE_URL"):
        openrouter_config["base_url"] = base_url
    if model := os.getenv("OPENROUTER_CHAT_MODEL"):
        openrouter_config["chat_model"] = model

    # Ollama
    ollama_config = data["llm"]["providers"].setdefault("ollama", {})
    if base_url := os.getenv("OLLAMA_BASE_URL"):
        ollama_config["base_url"] = base_url
    if model := os.getenv("OLLAMA_CHAT_MODEL"):
        ollama_config["chat_model"] = model
    if model := os.getenv("OLLAMA_VISION_MODEL"):
        ollama_config["vision_model"] = model
    if model := os.getenv("OLLAMA_EMBED_MODEL"):
        ollama_config["embed_model"] = model

    # LiteLLM
    litellm_config = data["llm"]["providers"].setdefault("litellm", {})
    if model := os.getenv("LITELLM_CHAT_MODEL"):
        litellm_config["chat_model"] = model
    if model := os.getenv("LITELLM_VISION_MODEL"):
        litellm_config["vision_model"] = model
    if model := os.getenv("LITELLM_EMBED_MODEL"):
        litellm_config["embed_model"] = model

    # LlamaCPP
    llamacpp_config = data["llm"]["providers"].setdefault("llamacpp", {})
    if model_path := os.getenv("LLAMACPP_MODEL_PATH"):
        llamacpp_config["model_path"] = model_path
    if model := os.getenv("LLAMACPP_CHAT_MODEL"):
        llamacpp_config["chat_model"] = model

    # Tracing
    if tracing := os.getenv("NOESIUM_OPIK_TRACING"):
        data.setdefault("tracing", {})["enabled"] = tracing.lower() == "true"

    # Logging
    if log_level := os.getenv("LOG_LEVEL"):
        data.setdefault("logging", {})["level"] = log_level
    if file_level := os.getenv("NOESIUM_FILE_LOG_LEVEL"):
        data.setdefault("logging", {})["file_level"] = file_level

    return data


# =============================================================================
# Utility Functions
# =============================================================================


def get_default_provider_config(provider: str) -> LLMProviderConfig:
    """Get default configuration for a specific provider.

    Args:
        provider: Provider name (openai, openrouter, ollama, litellm, llamacpp)

    Returns:
        Default LLMProviderConfig for the provider
    """
    defaults = {
        "openai": LLMProviderConfig(
            chat_model="gpt-4o",
            vision_model="gpt-4o",
            embed_model="text-embedding-3-small",
            structured_output=True,
        ),
        "openrouter": LLMProviderConfig(
            base_url="https://openrouter.ai/api/v1",
            chat_model="anthropic/claude-sonnet-4",
            vision_model="anthropic/claude-sonnet-4",
        ),
        "ollama": LLMProviderConfig(
            base_url="http://localhost:11434",
            chat_model="llama3.2",
            vision_model="llava",
            embed_model="nomic-embed-text",
        ),
        "litellm": LLMProviderConfig(
            chat_model="gpt-4o",
            vision_model="gpt-4o",
            embed_model="text-embedding-3-small",
        ),
        "llamacpp": LLMProviderConfig(),
    }
    return defaults.get(provider, LLMProviderConfig())


def init_default_config() -> FrameworkConfig:
    """Initialize a default configuration with all providers configured.

    This creates a config with sensible defaults for all supported providers.

    Returns:
        FrameworkConfig with default provider configurations
    """
    config = FrameworkConfig()

    # Set up default provider configs
    for provider_name in ["openai", "openrouter", "ollama", "litellm", "llamacpp"]:
        config.llm.providers[provider_name] = get_default_provider_config(provider_name)

    return config


__all__ = [
    # Models
    "FrameworkConfig",
    "LLMConfig",
    "LLMProviderConfig",
    "AgentConfig",
    "ToolsConfig",
    "ToolkitConfigEntry",
    "MCPServerConfig",
    "SubagentsConfig",
    "AgentSubagentConfig",
    "CliSubagentConfig",
    "MemoryConfig",
    "MemuMemoryConfig",
    "EventSourcedMemoryConfig",
    "TracingConfig",
    "OpikTracingConfig",
    "LoggingConfig",
    # Functions
    "load_config",
    "save_config",
    "get_config_path",
    "apply_env_overrides",
    "get_default_provider_config",
    "init_default_config",
]
