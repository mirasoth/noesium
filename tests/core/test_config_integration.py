"""Integration tests for NoeAgent configuration system.

Tests end-to-end configuration workflows, CLI commands, and integration
with NoeConfig.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from noesium.core.config import (
    AgentSubagentConfig,
    FrameworkConfig,
    init_default_config,
    load_config,
    save_config,
)
from noesium.noeagent.config import NoeConfig


class TestConfigIntegration:
    """Test configuration system integration."""

    def test_full_config_lifecycle(self):
        """Test complete config lifecycle: create, save, load, modify."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # 1. Create and save initial config
            config1 = FrameworkConfig()
            config1.llm.provider = "openai"
            config1.agent.max_iterations = 50
            save_config(config1, config_path)

            # 2. Load and verify (isolate environment)
            with patch.dict(os.environ, {}, clear=True):
                config2 = load_config(config_path)
                assert config2.llm.provider == "openai"
                assert config2.agent.max_iterations == 50

                # 3. Modify and save
                config2.llm.provider = "ollama"
                config2.agent.max_iterations = 100
                save_config(config2, config_path)

            # 4. Load again and verify changes (isolate environment)
            with patch.dict(os.environ, {}, clear=True):
                config3 = load_config(config_path)
                assert config3.llm.provider == "ollama"
                assert config3.agent.max_iterations == 100

    def test_config_with_env_precedence(self):
        """Test that environment variables take precedence over config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create config with ollama
            config = FrameworkConfig()
            config.llm.provider = "ollama"
            save_config(config, config_path)

            # Override with environment variable
            env = {
                "NOE_AGENT_CONFIG": str(config_path),
                "NOE_LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "test-key",
            }
            with patch.dict(os.environ, env):
                loaded = load_config()
                assert loaded.llm.provider == "openai"

    def test_config_with_mcp_servers(self):
        """Test configuration with MCP servers."""
        config = FrameworkConfig()
        config.tools.mcp_servers = [
            {
                "name": "filesystem",
                "command": "mcp-filesystem-server",
                "args": ["/allowed/path"],
                "env": {},
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            save_config(config, config_path)

            loaded = load_config(config_path)
            assert len(loaded.tools.mcp_servers) == 1
            assert loaded.tools.mcp_servers[0].name == "filesystem"

    def test_config_with_subagents(self):
        """Test configuration with subagents."""
        config = FrameworkConfig()
        config.subagents.builtin = [
            AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                description="Web automation agent",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            save_config(config, config_path)

            loaded = load_config(config_path)
            assert len(loaded.subagents.builtin) == 1
            assert loaded.subagents.builtin[0].name == "browser_use"
            assert loaded.subagents.builtin[0].agent_type == "browser_use"

    def test_config_with_subagents_builtin_config(self):
        """Test that builtin subagent config (e.g. headless) round-trips and is available via NoeConfig."""
        config = FrameworkConfig()
        config.subagents.builtin = [
            AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                description="Web automation agent",
                config={"headless": False},
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            save_config(config, config_path)

            loaded = load_config(config_path)
            assert len(loaded.subagents.builtin) == 1
            assert loaded.subagents.builtin[0].config == {"headless": False}

            with patch.dict(os.environ, {"NOE_AGENT_CONFIG": str(config_path)}):
                noe_config = NoeConfig.from_global_config()
                subagent = noe_config.get_builtin_subagent("browser_use")
                assert subagent is not None
                assert subagent["config"] == {"headless": False}

    def test_config_with_toolkit_configs(self):
        """Test configuration with toolkit-specific settings."""
        config = FrameworkConfig()
        config.tools.toolkit_configs = {
            "bash": {"timeout": 600, "shell": "/bin/zsh"},
            "python_executor": {"timeout": 300, "max_output_length": 20000},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            save_config(config, config_path)

            loaded = load_config(config_path)
            assert loaded.tools.toolkit_configs["bash"].timeout == 600
            assert loaded.tools.toolkit_configs["bash"].shell == "/bin/zsh"
            assert loaded.tools.toolkit_configs["python_executor"].max_output_length == 20000


class TestNoeConfigIntegration:
    """Test NoeConfig integration with global configuration."""

    def test_noe_config_from_global_config(self):
        """Test creating NoeConfig from global configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create global config
            global_config = FrameworkConfig()
            global_config.llm.provider = "ollama"
            global_config.llm.providers["ollama"] = {"chat_model": "llama3.2"}
            global_config.agent.max_iterations = 50
            global_config.tools.enabled_toolkits = ["bash", "python_executor"]
            save_config(global_config, config_path)

            # Load via NoeConfig (isolate environment to prevent overrides)
            env = {"NOE_AGENT_CONFIG": str(config_path)}
            with patch.dict(os.environ, env, clear=True):
                noe_config = NoeConfig.from_global_config()

                assert noe_config.llm_provider == "ollama"
                assert noe_config.model_name == "llama3.2"
                assert noe_config.max_iterations == 50
                assert "bash" in noe_config.enabled_toolkits

    def test_noe_config_get_builtin_subagent(self):
        """Test getting builtin subagent configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create global config with subagent (optional config for headless/headed)
            global_config = FrameworkConfig()
            global_config.subagents.builtin = [
                AgentSubagentConfig(
                    name="browser_use",
                    agent_type="browser_use",
                    description="Web automation",
                    config={"headless": False},
                )
            ]
            save_config(global_config, config_path)

            # Get subagent via NoeConfig
            with patch.dict(os.environ, {"NOE_AGENT_CONFIG": str(config_path)}):
                noe_config = NoeConfig.from_global_config()
                subagent = noe_config.get_builtin_subagent("browser_use")

                assert subagent is not None
                assert subagent["name"] == "browser_use"
                assert subagent["agent_type"] == "browser_use"
                assert subagent["config"] == {"headless": False}

    def test_noe_config_ask_mode_overrides(self):
        """Test that ask mode applies correct overrides."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create global config in agent mode
            global_config = FrameworkConfig()
            global_config.agent.mode = "ask"
            global_config.agent.max_iterations = 50
            global_config.tools.enabled_toolkits = ["bash", "python_executor"]
            save_config(global_config, config_path)

            # Load and check overrides
            with patch.dict(os.environ, {"NOE_AGENT_CONFIG": str(config_path)}):
                noe_config = NoeConfig.from_global_config()
                effective = noe_config.effective()

                # Ask mode should force these overrides
                assert effective.max_iterations == 1
                assert effective.enabled_toolkits == []
                assert effective.permissions == []
                assert effective.persist_memory is False


class TestConfigCLI:
    """Test configuration CLI commands."""

    def test_cli_config_path(self, capsys, monkeypatch):
        """Test 'noeagent config path' command."""
        from noesium.noeagent.__main__ import cmd_config_path

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = Path(tmpdir) / "custom_config.json"
            monkeypatch.setenv("NOE_AGENT_CONFIG", str(custom_path))

            cmd_config_path()
            captured = capsys.readouterr()
            assert str(custom_path) in captured.out

    def test_cli_config_show(self, capsys, monkeypatch):
        """Test 'noeagent config show' command."""
        from noesium.noeagent.__main__ import cmd_config_show

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            monkeypatch.setenv("NOE_AGENT_CONFIG", str(config_path))

            # Create config
            config = FrameworkConfig()
            config.llm.provider = "ollama"
            save_config(config, config_path)

            cmd_config_show(None)
            captured = capsys.readouterr()
            assert "ollama" in captured.out

    def test_cli_config_show_key(self, capsys, monkeypatch):
        """Test 'noeagent config show -k llm.provider' command."""
        from noesium.noeagent.__main__ import cmd_config_show

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            monkeypatch.setenv("NOE_AGENT_CONFIG", str(config_path))

            # Create config
            config = FrameworkConfig()
            config.llm.provider = "openai"
            save_config(config, config_path)

            cmd_config_show("llm.provider")
            captured = capsys.readouterr()
            assert "openai" in captured.out

    def test_cli_config_init(self, capsys, monkeypatch):
        """Test 'noeagent config init' command."""
        from noesium.noeagent.__main__ import cmd_config_init

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            monkeypatch.setenv("NOE_AGENT_CONFIG", str(config_path))

            # Mock user input
            monkeypatch.setattr("builtins.input", lambda _: "y")

            cmd_config_init("openai")
            capsys.readouterr()

            # Verify config was created
            assert config_path.exists()
            loaded = load_config(config_path)
            assert loaded.llm.provider == "openai"

    def test_cli_config_set(self, capsys, monkeypatch):
        """Test 'noeagent config set' command."""
        from noesium.noeagent.__main__ import cmd_config_set

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Set config path and isolate environment
            env = {"NOE_AGENT_CONFIG": str(config_path)}
            with patch.dict(os.environ, env, clear=True):
                # Create initial config
                config = FrameworkConfig()
                save_config(config, config_path)

                # Set a value
                cmd_config_set("llm.provider", "ollama")
                captured = capsys.readouterr()
                assert "Set llm.provider = ollama" in captured.out

                # Verify change
                loaded = load_config(config_path)
                assert loaded.llm.provider == "ollama"


class TestConfigPersistence:
    """Test configuration persistence and recovery."""

    def test_config_persists_across_sessions(self):
        """Test that configuration persists across multiple load/save cycles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Session 1: Create and save
            config1 = FrameworkConfig()
            config1.llm.provider = "openai"
            config1.agent.max_iterations = 30
            save_config(config1, config_path)

            # Session 2: Load and modify (isolate environment)
            with patch.dict(os.environ, {}, clear=True):
                config2 = load_config(config_path)
                config2.llm.provider = "ollama"
                config2.tools.enabled_toolkits.append("arxiv")
                save_config(config2, config_path)

            # Session 3: Load and verify all changes (isolate environment)
            with patch.dict(os.environ, {}, clear=True):
                config3 = load_config(config_path)
                assert config3.llm.provider == "ollama"
                assert config3.agent.max_iterations == 30
                assert "arxiv" in config3.tools.enabled_toolkits

    def test_config_handles_missing_fields(self):
        """Test that loading config with missing fields uses defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create minimal config
            minimal_config = {"version": "1.0", "llm": {"provider": "openai"}}
            with open(config_path, "w") as f:
                json.dump(minimal_config, f)

            # Load and verify defaults are applied
            config = load_config(config_path)
            assert config.agent.max_iterations == 25  # Default value
            assert "bash" in config.tools.enabled_toolkits  # Default value


class TestProviderConfiguration:
    """Test multi-provider configuration scenarios."""

    def test_multiple_providers_config(self):
        """Test configuration with multiple LLM providers."""
        config = init_default_config()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            save_config(config, config_path)

            # Load with environment isolation
            with patch.dict(os.environ, {}, clear=True):
                loaded = load_config(config_path)

                # Verify all providers are present
                assert "openai" in loaded.llm.providers
                assert "ollama" in loaded.llm.providers
                assert "openrouter" in loaded.llm.providers
                assert "litellm" in loaded.llm.providers
                assert "llamacpp" in loaded.llm.providers

                # Verify each has appropriate configuration
                assert loaded.llm.providers["openai"].chat_model == "gpt-4o"
                assert loaded.llm.providers["ollama"].base_url == "http://localhost:11434"

    def test_provider_switching_via_env(self):
        """Test switching providers via environment variable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create config with multiple providers
            config = init_default_config()
            save_config(config, config_path)

            # Test switching to different providers
            for provider in ["openai", "ollama", "openrouter"]:
                with patch.dict(os.environ, {"NOESIUM_CONFIG": str(config_path), "NOESIUM_LLM_PROVIDER": provider}):
                    loaded = load_config()
                    assert loaded.llm.provider == provider
