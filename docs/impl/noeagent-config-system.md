# NoeAgent Configuration System Design

## Overview

This document describes the configuration system for NoeAgent, providing a centralized, flexible, and hierarchical configuration management approach.

## Configuration Hierarchy

Configuration values are loaded with the following precedence (highest to lowest):

1. **Environment Variables** - Always take highest precedence
2. **Config File** - JSON configuration file
3. **Default Values** - Hard-coded defaults in code

## Configuration File Location

### Config File Path Resolution

The configuration file location is determined in this order:

1. **Environment Variable**: `NOE_AGENT_CONFIG=/path/to/config.json`
   - If set, use this path directly
   - Allows complete customization of config location

2. **Default Location**: `~/.noeagent/config.json`
   - Standard location for NoeAgent configuration
   - Directory: `$HOME/.noeagent/`

### Directory Structure

```
~/.noeagent/
├── config.json           # Unified configuration file
├── memory/              # Memory storage (memu)
├── sessions/              # Session storage
├── logs/                # Log files
└── data/                # Other persistent data
```

## Configuration File Format

### Complete Schema

```json
{
  "version": "1.0",

  "llm": {
    "provider": "openai",
    "providers": {
      "openai": {
        "api_key": null,
        "base_url": null,
        "chat_model": "gpt-4o",
        "vision_model": "gpt-4o",
        "embed_model": "text-embedding-3-small",
        "structured_output": true
      },
      "openrouter": {
        "api_key": null,
        "base_url": "https://openrouter.ai/api/v1",
        "chat_model": "anthropic/claude-sonnet-4",
        "vision_model": "anthropic/claude-sonnet-4"
      },
      "ollama": {
        "base_url": "http://localhost:11434",
        "chat_model": "llama3.2",
        "vision_model": "llava",
        "embed_model": "nomic-embed-text"
      },
      "litellm": {
        "chat_model": "gpt-4o",
        "vision_model": "gpt-4o",
        "embed_model": "text-embedding-3-small"
      },
      "llamacpp": {
        "model_path": null,
        "chat_model": null
      }
    }
  },

  "agent": {
    "mode": "agent",
    "max_iterations": 25,
    "max_tool_calls_per_step": 5,
    "reflection_interval": 3,
    "planning_model": null
  },

  "tools": {
    "enabled_toolkits": [  // here is the default enabled
      "bash",
      "file_edit",
      "document",
      "image",
      "python_executor",
      "tabular_data",
      "wizsearch",
      "user_interaction"
    ],
    "toolkit_configs": {
      "bash": {
        "timeout": 300,
        "shell": "/bin/bash"
      },
      "python_executor": {
        "timeout": 300,
        "max_output_length": 10000
      }
    },
    "mcp_servers": [
      {
        "name": "filesystem",
        "command": "mcp-filesystem-server",
        "args": ["/path/to/allowed/dir"],
        "env": {}
      }
    ],
    "permissions": [
      "fs:read",
      "fs:write",
      "net:outbound",
      "shell:execute"
    ]
  },

  "subagents": {
    "enabled": true,
    "max_depth": 2,
    "agent_subagents": [
      {
        "name": "browser_use",
        "agent_type": "browser_use",
        "description": "Web automation and browser control agent"
      },
      {
        "name": "tacitus",
        "agent_type": "tacitus",
        "description": "Advanced research and analysis agent"
      }
    ],
    "cli_subagents": []
  },

  "memory": {
    "providers": ["working", "event_sourced", "memu"],
    "persist": true,
    "memu": {
      "memory_dir": "~/.noeagent/memory",
      "user_id": "default_user"
    },
    "event_sourced": {
      "db_path": "~/.noeagent/data/events.db"
    }
  },

  "tracing": {
    "enabled": false,
    "provider": "opik",
    "opik": {
      "api_key": null,
      "workspace": null
    }
  },

  "logging": {
    "level": "INFO",
    "file": "~/.noeagent/logs/noeagent.log",
    "rotation": "10 MB",
    "retention": "7 days"
  },

  "working_directory": null
}
```

## Environment Variables

### Core Configuration

| Environment Variable | Config Path | Description | Default |
|---------------------|-------------|-------------|---------|
| `NOE_AGENT_CONFIG` | - | Path to config file | `~/.noeagent/config.json` |
| `NOESIUM_LLM_PROVIDER` | `llm.provider` | Default LLM provider | `openai` |
| `NOESIUM_EMBEDDING_DIMS` | - | Embedding dimensions | `768` |

### LLM Provider Configuration

Provider-specific environment variables override config file values:

#### OpenAI
- `OPENAI_API_KEY` - API key
- `OPENAI_BASE_URL` - Base URL (for proxies)
- `OPENAI_CHAT_MODEL` - Chat model name
- `OPENAI_VISION_MODEL` - Vision model name
- `OPENAI_EMBED_MODEL` - Embedding model name

#### OpenRouter
- `OPENROUTER_API_KEY` - API key
- `OPENROUTER_BASE_URL` - Base URL
- `OPENROUTER_CHAT_MODEL` - Chat model name

#### Ollama
- `OLLAMA_BASE_URL` - Server URL
- `OLLAMA_CHAT_MODEL` - Chat model name
- `OLLAMA_VISION_MODEL` - Vision model name
- `OLLAMA_EMBED_MODEL` - Embedding model name

#### LiteLLM
- `LITELLM_CHAT_MODEL` - Chat model identifier
- `LITELLM_VISION_MODEL` - Vision model identifier
- `LITELLM_EMBED_MODEL` - Embedding model identifier

#### LlamaCPP
- `LLAMACPP_MODEL_PATH` - Path to model
- `LLAMACPP_CHAT_MODEL` - Model name

### Tracing
- `NOESIUM_OPIK_TRACING` - Enable OPIK tracing (`true`/`false`)

### Logging
- `LOG_LEVEL` - Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

## Configuration Sections

### 1. LLM Configuration

The `llm` section configures language model providers:

```json
{
  "llm": {
    "provider": "openai",
    "providers": {
      "openai": { ... },
      "ollama": { ... }
    }
  }
}
```

**Fields:**
- `provider` (string): Default provider name
- `providers` (object): Provider-specific configurations

**Provider Config Fields:**
- `api_key` (string, optional): API key (can use env var)
- `base_url` (string, optional): Custom base URL
- `chat_model` (string): Model for chat completion
- `vision_model` (string, optional): Model for vision tasks
- `embed_model` (string, optional): Model for embeddings
- `structured_output` (bool): Enable structured output

### 2. Agent Configuration

The `agent` section controls agent behavior:

```json
{
  "agent": {
    "mode": "agent",
    "max_iterations": 25,
    "max_tool_calls_per_step": 5,
    "reflection_interval": 3,
    "planning_model": null
  }
}
```

**Fields:**
- `mode` (string): Agent mode - `"ask"` or `"agent"`
- `max_iterations` (int): Maximum reasoning iterations
- `max_tool_calls_per_step` (int): Tool calls per step limit
- `reflection_interval` (int): Steps between reflections
- `planning_model` (string, optional): Model for planning (defaults to chat model)

### 3. Tools Configuration

The `tools` section manages tool availability and behavior:

```json
{
  "tools": {
    "enabled_toolkits": ["bash", "python_executor", "file_edit"],
    "toolkit_configs": {
      "bash": {
        "timeout": 300
      }
    },
    "mcp_servers": [...],
    "permissions": ["fs:read", "fs:write"]
  }
}
```

**Fields:**
- `enabled_toolkits` (list): List of toolkit names to enable
- `toolkit_configs` (object): Toolkit-specific configurations
- `mcp_servers` (list): MCP server configurations
- `permissions` (list): Permission grants

**Available Toolkits:**
- `bash` - Shell command execution
- `python_executor` - Python code execution
- `file_edit` - File read/write/edit
- `memory` - Memory management
- `document` - Document processing
- `image` - Image processing
- `video` - Video processing
- `audio` - Audio processing
- `wizsearch` - Wiz search integration
- `jina_research` - Jina research
- `arxiv` - ArXiv paper search
- `serper` - Serper search
- `wikipedia` - Wikipedia search
- `github` - GitHub integration
- `gmail` - Gmail integration
- `tabular_data` - Data analysis
- `user_interaction` - User prompts

### 4. Subagents Configuration

The `subagents` section configures subagent behavior:

```json
{
  "subagents": {
    "enabled": true,
    "max_depth": 2,
    "builtin": [
      {
        "name": "browser_use",
        "agent_type": "browser_use",
        "description": "Web automation and browser control agent"
      },
      {
        "name": "tacitus",
        "agent_type": "tacitus",
        "description": "Advanced research and analysis agent"
      }
    ],
    "external": []
  }
}
```

**Fields:**
- `enabled` (bool): Enable subagent spawning
- `max_depth` (int): Maximum nesting depth (default: 2)
- `builtin` (list): Built-in agent subagent configurations (in-process agents)
- `external` (list): External CLI subagent configurations (spawned processes)

**Built-in Subagent Fields:**
- `name` (string): Subagent identifier
- `agent_type` (string): Agent type from available agents (e.g., "browser_use", "tacitus")
- `description` (string, optional): Description of subagent purpose

**Available Agent Types:**
- `browser_use` - Web automation and browser control (from `noesium.subagents.bu`)
- `tacitus` - Advanced research and analysis (from `noesium.subagents.tacitus`)
- `askura` - Conversation-style agent (from `noesium.subagents.askura`)
- `t2` - Task-specific agents (from `noesium.subagents.t2`)

**External Subagent Fields:**
- `name` (string): Subagent identifier
- `command` (string): Executable command
- `args` (list): Command arguments
- `env` (object): Environment variables
- `timeout` (int): Timeout in seconds
- `restart_policy` (string): Restart behavior
- `task_types` (list): Supported task types

**Subagent Behavior:**
- **In-process spawning**: Child NoeAgent instances spawned within the same process
- **Depth tracking**: Prevents infinite recursion with `max_depth` limit
- **Agent delegation**: Specific agent types (browser_use, tacitus) can be delegated tasks
- **External daemons**: External processes that run as daemons for specific task types

### 5. Memory Configuration

The `memory` section configures memory systems:

```json
{
  "memory": {
    "providers": ["working", "event_sourced", "memu"],
    "persist": true,
    "session_logging": true,
    "session_log_dir": "~/.noeagent/sessions",
    "memu": {
      "memory_dir": "~/.noeagent/memory",
      "user_id": "default_user"
    },
    "event_sourced": {
      "db_path": "~/.noeagent/data/events.db"
    }
  }
}
```

**Fields:**
- `providers` (list): Enabled memory providers
- `persist` (bool): Persist memory across sessions
- `session_logging` (bool): Enable session logging
- `session_log_dir` (string): Directory for session logs
- `memu` (object): Memu-specific config
- `event_sourced` (object): Event-sourced memory config

**Memory Providers:**
- `working` - Working memory (short-term, in-memory storage)
- `event_sourced` - Event-sourced memory (append-only event log with SQLite backend)
- `memu` - Long-term memory with semantic retrieval (vector-based)

**Memory Tiers:**
- **Working Memory**: Fast, ephemeral storage for current context
- **Event-Sourced Memory**: Durable event log for replay and audit
- **Memu Memory**: Semantic long-term memory with vector retrieval

**Provider Manager:**
The memory system uses a provider-based architecture (`ProviderMemoryManager`) that:
- Routes operations to registered providers
- Supports provider-specific queries and filtering
- Enables tier-based memory organization
- Provides unified recall across multiple providers

### 6. Tracing Configuration

The `tracing` section configures observability:

```json
{
  "tracing": {
    "enabled": false,
    "provider": "opik",
    "opik": {
      "use_local": true,
      "local_url": "http://localhost:5173",
      "api_key": null,
      "workspace": null,
      "project_name": "noesium-llm",
      "url": null
    }
  }
}
```

**Fields:**
- `enabled` (bool): Enable Opik tracing (maps to `NOESIUM_OPIK_TRACING`)
- `provider` (string): Tracing provider (currently only "opik" supported)
- `opik` (object): OPIK-specific config

**Opik Configuration:**
- `use_local` (bool): Use local Opik deployment (default: true)
- `local_url` (string): Local Opik URL (default: http://localhost:5173)
- `api_key` (string, optional): API key for Comet ML/Opik cloud
- `workspace` (string, optional): Workspace name for cloud
- `project_name` (string): Project name for organizing traces (default: "noesium-llm")
- `url` (string, optional): Custom Opik URL for cloud deployment

**Environment Variable Overrides:**
- `NOESIUM_OPIK_TRACING`: Global toggle for Opik tracing (default: false)
- `OPIK_USE_LOCAL`: Use local Opik deployment (default: true)
- `OPIK_LOCAL_URL`: Local Opik URL
- `OPIK_API_KEY`: API key for Comet ML/Opik (only needed for cloud)
- `OPIK_WORKSPACE`: Workspace name
- `OPIK_PROJECT_NAME`: Project name for organizing traces
- `OPIK_URL`: Custom Opik URL (for cloud deployment)
- `OPIK_TRACING`: Enable/disable tracing (default: true if enabled globally)

**Usage Modes:**
1. **Local Mode** (default): Runs Opik locally at http://localhost:5173
2. **Cloud Mode**: Connect to Comet ML/Opik cloud with API key

### 7. Logging Configuration

The `logging` section configures logging:

```json
{
  "logging": {
    "level": "INFO",
    "file": "~/.noeagent/logs/noeagent.log",
    "rotation": "10 MB",
    "retention": "7 days"
  }
}
```

**Fields:**
- `level` (string): Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `file` (string): Log file path
- `rotation` (string): Rotation size/time
- `retention` (string): Retention period

## Implementation Guide

### 1. Create Config Module

Create `noesium/core/config.py`:

```python
"""NoeAgent Configuration System"""
import os
import json
from pathlib import Path
from typing import Any, Optional, Dict, List
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# Constants
NOE_AGENT_HOME = Path.home() / ".noeagent"
DEFAULT_CONFIG_PATH = NOE_AGENT_HOME / "config.json"
CONFIG_VERSION = "1.0"


class LLMProviderConfig(BaseModel):
    """Configuration for a single LLM provider"""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    chat_model: Optional[str] = None
    vision_model: Optional[str] = None
    embed_model: Optional[str] = None
    structured_output: bool = True


class LLMConfig(BaseModel):
    """LLM configuration"""
    provider: str = Field(default_factory=lambda: os.getenv("NOESIUM_LLM_PROVIDER", "openai"))
    providers: Dict[str, LLMProviderConfig] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """Agent behavior configuration"""
    mode: str = "agent"  # "ask" or "agent"
    max_iterations: int = 25
    max_tool_calls_per_step: int = 5
    reflection_interval: int = 3
    planning_model: Optional[str] = None


class MCPServerConfig(BaseModel):
    """MCP server configuration"""
    name: str
    command: str
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)


class ToolkitConfigEntry(BaseModel):
    """Toolkit-specific configuration"""
    timeout: Optional[int] = None
    shell: Optional[str] = None
    max_output_length: Optional[int] = None


class ToolsConfig(BaseModel):
    """Tools configuration"""
    enabled_toolkits: List[str] = Field(default_factory=lambda: [
        "wizsearch", "jina_research", "bash", "python_executor",
        "file_edit", "memory", "document", "image", "tabular_data",
        "user_interaction"
    ])
    toolkit_configs: Dict[str, ToolkitConfigEntry] = Field(default_factory=dict)
    mcp_servers: List[MCPServerConfig] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=lambda: [
        "fs:read", "fs:write", "net:outbound", "shell:execute"
    ])


class AgentSubagentConfig(BaseModel):
    """Built-in agent subagent configuration"""
    name: str
    agent_type: str  # browser_use, tacitus, askura, t2
    description: Optional[str] = None


class CliSubagentConfig(BaseModel):
    """CLI subagent configuration"""
    name: str
    command: str
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    timeout: int = 300
    restart_policy: str = "on-failure"
    task_types: List[str] = Field(default_factory=list)


class SubagentsConfig(BaseModel):
    """Subagents configuration"""
    enabled: bool = True
    max_depth: int = 2
    agent_subagents: List[AgentSubagentConfig] = Field(default_factory=list)
    cli_subagents: List[CliSubagentConfig] = Field(default_factory=list)


class MemuMemoryConfig(BaseModel):
    """Memu memory configuration"""
    memory_dir: str = str(NOE_AGENT_HOME / "memory")
    user_id: str = "default_user"


class EventSourcedMemoryConfig(BaseModel):
    """Event-sourced memory configuration"""
    db_path: str = str(NOE_AGENT_HOME / "data" / "events.db")


class MemoryConfig(BaseModel):
    """Memory configuration"""
    providers: List[str] = Field(default_factory=lambda: ["working", "event_sourced", "memu"])
    persist: bool = True
    session_logging: bool = True
    session_log_dir: str = str(NOE_AGENT_HOME / "sessions")
    memu: MemuMemoryConfig = Field(default_factory=MemuMemoryConfig)
    event_sourced: EventSourcedMemoryConfig = Field(default_factory=EventSourcedMemoryConfig)


class OpikTracingConfig(BaseModel):
    """OPIK tracing configuration"""
    use_local: bool = True
    local_url: str = "http://localhost:5173"
    api_key: Optional[str] = None
    workspace: Optional[str] = None
    project_name: str = "noesium-llm"
    url: Optional[str] = None


class TracingConfig(BaseModel):
    """Tracing configuration"""
    enabled: bool = Field(default_factory=lambda: os.getenv("NOESIUM_OPIK_TRACING", "false").lower() == "true")
    provider: str = "opik"
    opik: OpikTracingConfig = Field(default_factory=OpikTracingConfig)


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    file: str = str(NOE_AGENT_HOME / "logs" / "noeagent.log")
    rotation: str = "10 MB"
    retention: str = "7 days"


class NoeAgentConfig(BaseModel):
    """Main NoeAgent configuration"""
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


def get_config_path() -> Path:
    """Get configuration file path"""
    config_path = os.getenv("NOE_AGENT_CONFIG")
    if config_path:
        return Path(config_path)
    return DEFAULT_CONFIG_PATH


def load_config(config_path: Optional[Path] = None) -> NoeAgentConfig:
    """Load configuration from file"""
    if config_path is None:
        config_path = get_config_path()

    # Create default config if file doesn't exist
    if not config_path.exists():
        config = NoeAgentConfig()
        save_config(config, config_path)
        return config

    # Load from file
    with open(config_path, 'r') as f:
        data = json.load(f)

    # Apply environment variable overrides
    data = apply_env_overrides(data)

    return NoeAgentConfig(**data)


def save_config(config: NoeAgentConfig, config_path: Optional[Path] = None):
    """Save configuration to file"""
    if config_path is None:
        config_path = get_config_path()

    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config
    with open(config_path, 'w') as f:
        json.dump(config.model_dump(exclude_none=True), f, indent=2)


def apply_env_overrides(data: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to config data"""

    # LLM Provider
    if provider := os.getenv("NOESIUM_LLM_PROVIDER"):
        data.setdefault("llm", {})["provider"] = provider

    # OpenAI
    if api_key := os.getenv("OPENAI_API_KEY"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("openai", {})["api_key"] = api_key
    if base_url := os.getenv("OPENAI_BASE_URL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("openai", {})["base_url"] = base_url
    if model := os.getenv("OPENAI_CHAT_MODEL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("openai", {})["chat_model"] = model
    if model := os.getenv("OPENAI_VISION_MODEL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("openai", {})["vision_model"] = model
    if model := os.getenv("OPENAI_EMBED_MODEL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("openai", {})["embed_model"] = model

    # OpenRouter
    if api_key := os.getenv("OPENROUTER_API_KEY"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("openrouter", {})["api_key"] = api_key
    if base_url := os.getenv("OPENROUTER_BASE_URL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("openrouter", {})["base_url"] = base_url
    if model := os.getenv("OPENROUTER_CHAT_MODEL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("openrouter", {})["chat_model"] = model

    # Ollama
    if base_url := os.getenv("OLLAMA_BASE_URL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("ollama", {})["base_url"] = base_url
    if model := os.getenv("OLLAMA_CHAT_MODEL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("ollama", {})["chat_model"] = model
    if model := os.getenv("OLLAMA_VISION_MODEL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("ollama", {})["vision_model"] = model
    if model := os.getenv("OLLAMA_EMBED_MODEL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("ollama", {})["embed_model"] = model

    # LiteLLM
    if model := os.getenv("LITELLM_CHAT_MODEL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("litellm", {})["chat_model"] = model
    if model := os.getenv("LITELLM_VISION_MODEL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("litellm", {})["vision_model"] = model
    if model := os.getenv("LITELLM_EMBED_MODEL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("litellm", {})["embed_model"] = model

    # LlamaCPP
    if model_path := os.getenv("LLAMACPP_MODEL_PATH"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("llamacpp", {})["model_path"] = model_path
    if model := os.getenv("LLAMACPP_CHAT_MODEL"):
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault("llamacpp", {})["chat_model"] = model

    return data
```

### 2. Update Constants Module

Update `noesium/core/consts.py`:

```python
"""Global constants for NoeAgent"""
from pathlib import Path

# LLM Model Constants
GEMINI_PRO = "gemini-pro"
GEMINI_FLASH = "gemini-flash"

# Embedding Constants
DEFAULT_EMBEDDING_DIMS = 768

# Configuration Constants
NOE_AGENT_HOME = Path.home() / ".noeagent"
DEFAULT_CONFIG_PATH = NOE_AGENT_HOME / "config.json"
CONFIG_VERSION = "1.0"

# Default Directories
NOE_AGENT_LOGS_DIR = NOE_AGENT_HOME / "logs"
NOE_AGENT_MEMORY_DIR = NOE_AGENT_HOME / "memory"
NOE_AGENT_DATA_DIR = NOE_AGENT_HOME / "data"
```

### 3. Integration with NoeConfig

Update `noesium/noe/config.py` to use the new config system:

```python
from noesium.core.config import load_config, NoeAgentConfig

class NoeConfig(BaseModel):
    """Noe-specific configuration (extends NoeAgentConfig)"""

    @classmethod
    def from_global_config(cls) -> "NoeConfig":
        """Load NoeConfig from global configuration"""
        global_config = load_config()

        return cls(
            mode=global_config.agent.mode,
            llm_provider=global_config.llm.provider,
            model_name=global_config.llm.providers.get(global_config.llm.provider, {}).get("chat_model"),
            planning_model=global_config.agent.planning_model,
            max_iterations=global_config.agent.max_iterations,
            max_tool_calls_per_step=global_config.agent.max_tool_calls_per_step,
            reflection_interval=global_config.agent.reflection_interval,
            interface_mode="library",
            session_log_dir=global_config.memory.session_log_dir,
            enable_session_logging=global_config.memory.session_logging,
            enabled_toolkits=global_config.tools.enabled_toolkits,
            mcp_servers=[s.model_dump() for s in global_config.tools.mcp_servers],
            memory_providers=global_config.memory.providers,
            memu_memory_dir=global_config.memory.memu.memory_dir,
            memu_user_id=global_config.memory.memu.user_id,
            persist_memory=global_config.memory.persist,
            working_directory=global_config.working_directory,
            permissions=global_config.tools.permissions,
            enable_subagents=global_config.subagents.enabled,
            subagent_max_depth=global_config.subagents.max_depth,
            cli_subagents=[s.model_dump() for s in global_config.subagents.cli_subagents],
        )

    def get_agent_subagent(self, name: str) -> Optional[dict]:
        """Get agent subagent configuration by name"""
        from noesium.core.config import load_config
        global_config = load_config()
        for subagent in global_config.subagents.agent_subagents:
            if subagent.name == name:
                return subagent.model_dump()
        return None
```

### 4. Config Migration System

Create `noesium/core/config_migration.py`:

```python
"""Configuration migration system"""
import json
from pathlib import Path
from typing import Any, Dict
from packaging import version


def migrate_config(data: Dict[str, Any], from_version: str) -> Dict[str, Any]:
    """Migrate config to latest version"""
    current_version = data.get("version", "0.0")

    migrations = {
        "0.0": migrate_0_0_to_1_0,
        # Future migrations:
        # "1.0": migrate_1_0_to_1_1,
    }

    while current_version in migrations:
        data = migrations[current_version](data)
        current_version = data["version"]

    return data


def migrate_0_0_to_1_0(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate from version 0.0 (no version) to 1.0"""
    # Add version field
    data["version"] = "1.0"

    # Restructure LLM config
    if "llm_provider" in data:
        provider = data.pop("llm_provider")
        data.setdefault("llm", {})["provider"] = provider

    # Move top-level fields to sections
    field_mappings = {
        "max_iterations": ("agent", "max_iterations"),
        "max_tool_calls_per_step": ("agent", "max_tool_calls_per_step"),
        "reflection_interval": ("agent", "reflection_interval"),
        "enabled_toolkits": ("tools", "enabled_toolkits"),
        "mcp_servers": ("tools", "mcp_servers"),
        "permissions": ("tools", "permissions"),
        "enable_subagents": ("subagents", "enabled"),
        "subagent_max_depth": ("subagents", "max_depth"),
        "cli_subagents": ("subagents", "cli_subagents"),
        "memory_providers": ("memory", "providers"),
        "persist_memory": ("memory", "persist"),
    }

    for old_key, (section, new_key) in field_mappings.items():
        if old_key in data:
            data.setdefault(section, {})[new_key] = data.pop(old_key)

    return data
```

### 5. CLI Integration

Add config commands to CLI (`noesium/cli.py`):

```python
import click
from pathlib import Path
from noesium.core.config import load_config, save_config, get_config_path, NoeAgentConfig


@click.group()
def config():
    """Configuration commands"""
    pass


@config.command()
@click.option('--key', '-k', help='Config key to show (e.g., llm.provider)')
def show(key: str):
    """Show current configuration"""
    config = load_config()

    if key:
        # Navigate nested keys
        value = config.model_dump()
        for k in key.split('.'):
            value = value.get(k)
            if value is None:
                click.echo(f"Key '{key}' not found")
                return
        click.echo(json.dumps(value, indent=2))
    else:
        click.echo(json.dumps(config.model_dump(exclude_none=True), indent=2))


@config.command()
def path():
    """Show config file path"""
    click.echo(str(get_config_path()))


@config.command()
@click.option('--provider', '-p', help='LLM provider name')
def init(provider: str):
    """Initialize config file with defaults"""
    config_path = get_config_path()

    if config_path.exists():
        if not click.confirm(f"Config file already exists at {config_path}. Overwrite?"):
            return

    config = NoeAgentConfig()
    if provider:
        config.llm.provider = provider

    save_config(config, config_path)
    click.echo(f"Created config file at {config_path}")


@config.command()
@click.argument('key')
@click.argument('value')
def set(key: str, value: str):
    """Set a configuration value"""
    config = load_config()

    # Parse key path
    keys = key.split('.')
    obj = config.model_dump()

    # Navigate to parent
    for k in keys[:-1]:
        obj = obj.setdefault(k, {})

    # Set value (try to parse as JSON, otherwise use string)
    try:
        obj[keys[-1]] = json.loads(value)
    except:
        obj[keys[-1]] = value

    # Save
    config = NoeAgentConfig(**obj)
    save_config(config)
    click.echo(f"Set {key} = {value}")
```

## Usage Examples

### 1. Using Environment Variables

```bash
# Set LLM provider
export NOESIUM_LLM_PROVIDER=openai

# Set OpenAI configuration
export OPENAI_API_KEY=sk-...
export OPENAI_CHAT_MODEL=gpt-4o

# Set custom config path
export NOE_AGENT_CONFIG=/path/to/custom/config.json

# Run NoeAgent
noe run "Your task"
```

### 2. Using Config File

Create `~/.noeagent/config.json`:

```json
{
  "version": "1.0",
  "llm": {
    "provider": "ollama",
    "providers": {
      "ollama": {
        "base_url": "http://localhost:11434",
        "chat_model": "llama3.2"
      }
    }
  },
  "agent": {
    "mode": "agent",
    "max_iterations": 30
  },
  "tools": {
    "enabled_toolkits": ["bash", "python_executor", "file_edit"]
  }
}
```

### 3. Programmatic Usage

```python
from noesium.core.config import load_config

# Load configuration
config = load_config()

# Access values
print(f"LLM Provider: {config.llm.provider}")
print(f"Chat Model: {config.llm.providers[config.llm.provider].chat_model}")
print(f"Max Iterations: {config.agent.max_iterations}")
print(f"Enabled Tools: {config.tools.enabled_toolkits}")

# Modify configuration
config.agent.max_iterations = 50
config.tools.enabled_toolkits.append("arxiv")

# Save changes
from noesium.core.config import save_config
save_config(config)
```

### 4. CLI Commands

```bash
# Show config path
noe config path

# Show current config
noe config show

# Show specific value
noe config show -k llm.provider

# Initialize config
noe config init --provider openai

# Set a value
noe config set llm.provider ollama
noe config set agent.max_iterations 30
```

## Migration Guide

### From Environment Variables Only

If you're currently using only environment variables:

1. Initialize config file:
   ```bash
   noe config init
   ```

2. The config system will automatically read your environment variables and apply them as overrides

3. Optionally, migrate env vars to config file:
   ```bash
   # Copy env values to config
   noe config set llm.providers.openai.api_key $OPENAI_API_KEY
   noe config set llm.providers.openai.chat_model $OPENAI_CHAT_MODEL
   ```

### From Old NoeConfig

If you have existing NoeConfig code:

1. Load from global config:
   ```python
   # Old way
   config = NoeConfig(
       llm_provider="openai",
       max_iterations=30
   )

   # New way
   from noesium.core.config import load_config
   global_config = load_config()
   noe_config = NoeConfig.from_global_config()
   ```

2. Environment variables still work and take precedence

3. Config file provides persistent storage for settings

## Best Practices

### 1. Configuration Management

- **Use config file for persistent settings**: Settings that don't change between runs
- **Use environment variables for secrets**: API keys, passwords, etc.
- **Use environment variables for environment-specific values**: Different values for dev/staging/prod

### 2. Security

- **Never commit API keys to config files**: Use environment variables or secret managers
- **Set file permissions**: `chmod 600 ~/.noeagent/config.json`
- **Use environment variable interpolation**: Reference env vars in config (future feature)

### 3. Organization

- **Use a single unified config file**: All settings in `~/.noeagent/config.json`
- **Document custom configs**: Add comments or maintain a separate documentation file
- **Version control configs**: Store template configs in repository, exclude actual config files with secrets

### 4. Validation

The configuration system validates:
- Required fields are present
- Field types are correct
- Values are within acceptable ranges
- Enum values are valid

## Future Enhancements

### 1. Config Profiles

Support multiple configuration profiles:

```json
{
  "profiles": {
    "dev": {
      "llm": { "provider": "ollama" }
    },
    "prod": {
      "llm": { "provider": "openai" }
    }
  }
}
```

Usage: `export NOE_AGENT_PROFILE=prod`

### 2. Environment Variable Interpolation

Allow referencing env vars in config:

```json
{
  "llm": {
    "providers": {
      "openai": {
        "api_key": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

### 3. Config Inheritance

Support config file inheritance:

```json
{
  "extends": "~/.noeagent/base-config.json",
  "llm": {
    "provider": "ollama"
  }
}
```

### 4. Schema Validation

Add JSON Schema for better validation:

```bash
noe config validate
```

### 5. Config Encryption

Encrypt sensitive fields:

```json
{
  "llm": {
    "providers": {
      "openai": {
        "api_key": "encrypted:..."
      }
    }
  }
}
```

## Summary

The NoeAgent configuration system provides:

1. **Flexible configuration hierarchy**: Env vars > Config file > Defaults
2. **Comprehensive coverage**: LLM, tools, subagents, memory, tracing, logging
3. **Type-safe configuration**: Using Pydantic for validation
4. **Easy migration**: Automatic migration from older config versions
5. **CLI management**: Commands to view, edit, and manage configuration
6. **Backward compatibility**: Existing environment variables continue to work
7. **Forward compatibility**: Version field and migration system for future changes

This design enables users to configure NoeAgent through multiple mechanisms while maintaining security, validation, and ease of use.
