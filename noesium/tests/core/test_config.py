"""Unit tests for NoeAgent configuration system.

Tests the configuration models, loading/saving, environment variable overrides,
and configuration migration.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from noesium.core.config import (
    AgentConfig,
    AgentSubagentConfig,
    CliSubagentConfig,
    FrameworkConfig,
    LLMConfig,
    LLMProviderConfig,
    LoggingConfig,
    MCPServerConfig,
    MemoryConfig,
    SubagentsConfig,
    ToolkitConfigEntry,
    ToolsConfig,
    TracingConfig,
    apply_env_overrides,
    get_config_path,
    get_default_provider_config,
    init_default_config,
    load_config,
    save_config,
)
from noesium.core.config_migration import (
    get_migration_version,
    migrate_0_0_to_1_0,
    migrate_config,
    needs_migration,
)
from noesium.core.consts import CONFIG_VERSION


class TestConfigModels:
    """Test configuration model classes."""

    def test_llm_provider_config_defaults(self):
        """Test LLMProviderConfig default values."""
        config = LLMProviderConfig()
        assert config.api_key is None
        assert config.base_url is None
        assert config.chat_model is None
        assert config.vision_model is None
        assert config.embed_model is None
        assert config.structured_output is True

    def test_llm_provider_config_with_values(self):
        """Test LLMProviderConfig with explicit values."""
        config = LLMProviderConfig(
            api_key="test-key",
            base_url="https://api.example.com",
            chat_model="gpt-4",
            vision_model="gpt-4-vision",
            embed_model="text-embedding-3-small",
            structured_output=False,
        )
        assert config.api_key == "test-key"
        assert config.base_url == "https://api.example.com"
        assert config.chat_model == "gpt-4"
        assert config.vision_model == "gpt-4-vision"
        assert config.embed_model == "text-embedding-3-small"
        assert config.structured_output is False

    def test_llm_config_defaults(self):
        """Test LLMConfig default values."""
        with patch.dict(os.environ, {"NOESIUM_LLM_PROVIDER": "openai"}):
            config = LLMConfig()
            assert config.provider == "openai"
            assert config.providers == {}

    def test_llm_config_with_providers(self):
        """Test LLMConfig with provider configurations."""
        config = LLMConfig(
            provider="openai",
            providers={
                "openai": LLMProviderConfig(chat_model="gpt-4o"),
                "ollama": LLMProviderConfig(chat_model="llama3.2"),
            },
        )
        assert config.provider == "openai"
        assert "openai" in config.providers
        assert "ollama" in config.providers
        assert config.providers["openai"].chat_model == "gpt-4o"
        assert config.providers["ollama"].chat_model == "llama3.2"

    def test_agent_config_defaults(self):
        """Test AgentConfig default values."""
        config = AgentConfig()
        assert config.mode == "agent"
        assert config.max_iterations == 25
        assert config.max_tool_calls_per_step == 5
        assert config.reflection_interval == 3
        assert config.planning_model is None

    def test_tools_config_defaults(self):
        """Test ToolsConfig default values."""
        config = ToolsConfig()
        assert "bash" in config.enabled_toolkits
        assert "python_executor" in config.enabled_toolkits
        assert "fs:read" in config.permissions
        assert "fs:write" in config.permissions
        assert config.mcp_servers == []
        assert config.toolkit_configs == {}

    def test_mcp_server_config(self):
        """Test MCPServerConfig."""
        config = MCPServerConfig(
            name="filesystem",
            command="mcp-filesystem-server",
            args=["/path/to/dir"],
            env={"API_KEY": "test"},
        )
        assert config.name == "filesystem"
        assert config.command == "mcp-filesystem-server"
        assert config.args == ["/path/to/dir"]
        assert config.env == {"API_KEY": "test"}

    def test_toolkit_config_entry(self):
        """Test ToolkitConfigEntry."""
        config = ToolkitConfigEntry(timeout=300, shell="/bin/bash")
        assert config.timeout == 300
        assert config.shell == "/bin/bash"

    def test_subagents_config_defaults(self):
        """Test SubagentsConfig default values."""
        config = SubagentsConfig()
        assert config.enabled is True
        assert config.max_depth == 2
        assert config.builtin == []
        assert config.external == []

    def test_agent_subagent_config(self):
        """Test AgentSubagentConfig."""
        config = AgentSubagentConfig(
            name="browser_use",
            agent_type="browser_use",
            description="Web automation agent",
        )
        assert config.name == "browser_use"
        assert config.agent_type == "browser_use"
        assert config.description == "Web automation agent"
        assert config.config is None

    def test_agent_subagent_config_with_config(self):
        """Test AgentSubagentConfig with optional config (e.g. headless for browser_use)."""
        config = AgentSubagentConfig(
            name="browser_use",
            agent_type="browser_use",
            description="Web automation agent",
            config={"headless": False},
        )
        assert config.config == {"headless": False}

    def test_cli_subagent_config(self):
        """Test CliSubagentConfig."""
        config = CliSubagentConfig(
            name="test-agent",
            command="test-command",
            args=["--flag"],
            env={"KEY": "value"},
            timeout=600,
        )
        assert config.name == "test-agent"
        assert config.command == "test-command"
        assert config.args == ["--flag"]
        assert config.env == {"KEY": "value"}
        assert config.timeout == 600

    def test_memory_config_defaults(self):
        """Test MemoryConfig default values."""
        config = MemoryConfig()
        assert "working" in config.providers
        assert "event_sourced" in config.providers
        assert "memu" in config.providers
        assert config.persist is True
        assert config.session_logging is True

    def test_tracing_config_defaults(self):
        """Test TracingConfig default values."""
        with patch.dict(os.environ, {"NOESIUM_OPIK_TRACING": "false"}):
            config = TracingConfig()
            assert config.enabled is False
            assert config.provider == "opik"
            assert config.opik.use_local is True

    def test_logging_config_defaults(self):
        """Test LoggingConfig default values."""
        with patch.dict(
            os.environ,
            {"LOG_LEVEL": "INFO", "NOESIUM_FILE_LOG_LEVEL": ""},
            clear=False,
        ):
            config = LoggingConfig()
            assert config.level == "INFO"
            # file_level may be None or empty string depending on .env
            assert config.file_level in (None, "")
            assert config.rotation == "10 MB"
            assert config.retention == "7 days"

    def test_noeagent_config_defaults(self):
        """Test FrameworkConfig default values."""
        config = FrameworkConfig()
        assert config.version == CONFIG_VERSION
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.agent, AgentConfig)
        assert isinstance(config.tools, ToolsConfig)
        assert isinstance(config.subagents, SubagentsConfig)
        assert isinstance(config.memory, MemoryConfig)
        assert isinstance(config.tracing, TracingConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert config.working_directory is None

    def test_noeagent_config_extra_fields(self):
        """Test that FrameworkConfig allows extra fields."""
        config = FrameworkConfig(custom_field="test")
        assert config.model_dump().get("custom_field") == "test"


class TestConfigLoading:
    """Test configuration loading and saving."""

    def test_get_config_path_default(self):
        """Test default config path resolution."""
        with patch.dict(os.environ, {}, clear=True):
            path = get_config_path()
            assert path.name == "config.json"
            assert ".noesium" in str(path)

    def test_get_config_path_from_env(self):
        """Test config path from environment variable."""
        with patch.dict(os.environ, {"NOESIUM_CONFIG": "/custom/path/config.json"}):
            path = get_config_path()
            assert path == Path("/custom/path/config.json")

    def test_load_config_creates_default(self):
        """Test that load_config creates default config if file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config = load_config(config_path)

            assert isinstance(config, FrameworkConfig)
            assert config_path.exists()

            # Verify the file was created
            with open(config_path) as f:
                data = json.load(f)
                assert data["version"] == CONFIG_VERSION

    def test_load_config_from_file(self):
        """Test loading config from existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create a config file
            config_data = {
                "version": "1.0",
                "llm": {"provider": "ollama", "providers": {"ollama": {"chat_model": "llama3.2"}}},
                "agent": {"max_iterations": 50},
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            # Load and verify (isolate environment to prevent overrides)
            with patch.dict(os.environ, {}, clear=True):
                config = load_config(config_path)
                assert config.llm.provider == "ollama"
                assert config.llm.providers["ollama"].chat_model == "llama3.2"
                assert config.agent.max_iterations == 50

    def test_load_config_empty_file_uses_defaults(self):
        """Test that empty config file {} is merged with defaults (e.g. ~/.noesium/config.json = {})."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text("{}")

            with patch.dict(os.environ, {}, clear=True):
                config = load_config(config_path)

            assert isinstance(config, FrameworkConfig)
            assert config.version == CONFIG_VERSION
            assert config.llm.provider == "openai"
            assert "bash" in config.tools.enabled_toolkits
            assert config.agent.max_iterations == 25

    def test_load_config_invalid_json_uses_defaults(self):
        """Test that invalid JSON in config file falls back to defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text("{ invalid }")

            with patch.dict(os.environ, {}, clear=True):
                config = load_config(config_path)

            assert isinstance(config, FrameworkConfig)
            assert config.llm.provider == "openai"
            assert "bash" in config.tools.enabled_toolkits

    def test_save_config(self):
        """Test saving configuration to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            config = FrameworkConfig()
            config.agent.max_iterations = 100
            config.llm.provider = "openai"

            save_config(config, config_path)

            # Verify saved data
            with open(config_path) as f:
                data = json.load(f)
                assert data["agent"]["max_iterations"] == 100
                assert data["llm"]["provider"] == "openai"

    def test_load_config_with_env_overrides(self):
        """Test that environment variables override config file values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create config file with ollama
            config_data = {
                "version": "1.0",
                "llm": {"provider": "ollama"},
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            # Override with environment variable
            with patch.dict(os.environ, {"NOESIUM_LLM_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"}):
                config = load_config(config_path)
                assert config.llm.provider == "openai"
                # Note: API key from env should be in providers config


class TestEnvironmentOverrides:
    """Test environment variable overrides."""

    def test_apply_env_overrides_llm_provider(self):
        """Test NOESIUM_LLM_PROVIDER override."""
        data = {}
        with patch.dict(os.environ, {"NOESIUM_LLM_PROVIDER": "ollama"}):
            result = apply_env_overrides(data)
            assert result["llm"]["provider"] == "ollama"

    def test_apply_env_overrides_openai(self):
        """Test OpenAI environment variable overrides."""
        data = {}
        env = {
            "OPENAI_API_KEY": "test-api-key",
            "OPENAI_BASE_URL": "https://custom.api.com",
            "OPENAI_CHAT_MODEL": "gpt-4-turbo",
        }
        with patch.dict(os.environ, env):
            result = apply_env_overrides(data)
            assert result["llm"]["providers"]["openai"]["api_key"] == "test-api-key"
            assert result["llm"]["providers"]["openai"]["base_url"] == "https://custom.api.com"
            assert result["llm"]["providers"]["openai"]["chat_model"] == "gpt-4-turbo"

    def test_apply_env_overrides_ollama(self):
        """Test Ollama environment variable overrides."""
        data = {}
        env = {
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_CHAT_MODEL": "llama3.2",
        }
        with patch.dict(os.environ, env):
            result = apply_env_overrides(data)
            assert result["llm"]["providers"]["ollama"]["base_url"] == "http://localhost:11434"
            assert result["llm"]["providers"]["ollama"]["chat_model"] == "llama3.2"

    def test_apply_env_overrides_tracing(self):
        """Test NOESIUM_OPIK_TRACING override."""
        data = {}
        with patch.dict(os.environ, {"NOESIUM_OPIK_TRACING": "true"}):
            result = apply_env_overrides(data)
            assert result["tracing"]["enabled"] is True

    def test_apply_env_overrides_logging(self):
        """Test LOG_LEVEL and NOESIUM_FILE_LOG_LEVEL overrides."""
        data = {}
        with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}, clear=False):
            result = apply_env_overrides(data)
            assert result["logging"]["level"] == "WARNING"

        data = {}
        with patch.dict(os.environ, {"NOESIUM_FILE_LOG_LEVEL": "DEBUG"}, clear=False):
            result = apply_env_overrides(data)
            assert result["logging"]["file_level"] == "DEBUG"


class TestConfigMigration:
    """Test configuration migration system."""

    def test_migrate_0_0_to_1_0_basic(self):
        """Test basic migration from version 0.0 to 1.0."""
        old_config = {
            "llm_provider": "openai",
            "model_name": "gpt-4",
            "max_iterations": 30,
        }
        result = migrate_0_0_to_1_0(old_config)

        assert result["version"] == "1.0"
        assert result["llm"]["provider"] == "openai"
        assert result["llm"]["providers"]["openai"]["chat_model"] == "gpt-4"
        assert result["agent"]["max_iterations"] == 30

    def test_migrate_0_0_to_1_0_tools(self):
        """Test migration of tools configuration."""
        old_config = {
            "enabled_toolkits": ["bash", "python_executor"],
            "permissions": ["fs:read", "fs:write"],
        }
        result = migrate_0_0_to_1_0(old_config)

        assert result["tools"]["enabled_toolkits"] == ["bash", "python_executor"]
        assert result["tools"]["permissions"] == ["fs:read", "fs:write"]

    def test_migrate_0_0_to_1_0_subagents(self):
        """Test migration of subagents configuration."""
        old_config = {
            "enable_subagents": True,
            "subagent_max_depth": 3,
        }
        result = migrate_0_0_to_1_0(old_config)

        assert result["subagents"]["enabled"] is True
        assert result["subagents"]["max_depth"] == 3

    def test_migrate_0_0_to_1_0_memory(self):
        """Test migration of memory configuration."""
        old_config = {
            "memory_providers": ["working", "memu"],
            "persist_memory": False,
        }
        result = migrate_0_0_to_1_0(old_config)

        assert result["memory"]["providers"] == ["working", "memu"]
        assert result["memory"]["persist"] is False

    def test_migrate_config_iterative(self):
        """Test that migrate_config applies migrations iteratively."""
        old_config = {"llm_provider": "openai"}
        result = migrate_config(old_config, "0.0")

        assert result["version"] == CONFIG_VERSION
        assert result["llm"]["provider"] == "openai"

    def test_get_migration_version(self):
        """Test version detection."""
        assert get_migration_version({}) == "0.0"
        assert get_migration_version({"version": "1.0"}) == "1.0"

    def test_needs_migration(self):
        """Test migration detection."""
        assert needs_migration({}) is True
        assert needs_migration({"version": "0.0"}) is True
        assert needs_migration({"version": CONFIG_VERSION}) is False


class TestUtilityFunctions:
    """Test utility functions."""

    def test_get_default_provider_config_openai(self):
        """Test default OpenAI provider config."""
        config = get_default_provider_config("openai")
        assert config.chat_model == "gpt-4o"
        assert config.vision_model == "gpt-4o"
        assert config.embed_model == "text-embedding-3-small"

    def test_get_default_provider_config_ollama(self):
        """Test default Ollama provider config."""
        config = get_default_provider_config("ollama")
        assert config.base_url == "http://localhost:11434"
        assert config.chat_model == "llama3.2"

    def test_get_default_provider_config_unknown(self):
        """Test default config for unknown provider."""
        config = get_default_provider_config("unknown")
        assert config.chat_model is None

    def test_init_default_config(self):
        """Test initialization of default config with all providers."""
        config = init_default_config()

        assert "openai" in config.llm.providers
        assert "ollama" in config.llm.providers
        assert "openrouter" in config.llm.providers
        assert "litellm" in config.llm.providers
        assert "llamacpp" in config.llm.providers

        # Verify each provider has appropriate defaults
        assert config.llm.providers["openai"].chat_model == "gpt-4o"
        assert config.llm.providers["ollama"].chat_model == "llama3.2"


class TestConfigNormalization:
    """Test configuration data normalization."""

    def test_normalize_builtin_dict(self):
        """Test normalization of builtin from dict to list."""
        from noesium.core.config import _normalize_config_data

        data = {"subagents": {"builtin": {"browser_use": {}}}}
        result = _normalize_config_data(data)

        assert result["subagents"]["builtin"] == []

    def test_normalize_external_dict(self):
        """Test normalization of external from dict to list."""
        from noesium.core.config import _normalize_config_data

        data = {"subagents": {"external": {"test": {}}}}
        result = _normalize_config_data(data)

        assert result["subagents"]["external"] == []

    def test_normalize_memory_providers_dict(self):
        """Test normalization of memory.providers from dict to list."""
        from noesium.core.config import _normalize_config_data

        data = {"memory": {"providers": {"working": {}, "memu": {}}}}
        result = _normalize_config_data(data)

        assert result["memory"]["providers"] == ["working", "memu"]

    def test_normalize_enabled_toolkits_dict(self):
        """Test normalization of tools.enabled_toolkits from dict to list."""
        from noesium.core.config import _normalize_config_data

        data = {"tools": {"enabled_toolkits": {"bash": {}, "python_executor": {}}}}
        result = _normalize_config_data(data)

        assert result["tools"]["enabled_toolkits"] == ["bash", "python_executor"]
