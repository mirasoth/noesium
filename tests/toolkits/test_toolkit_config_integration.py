"""Tests for toolkit-specific configuration integration."""

from noesium.core.config import (
    FrameworkConfig,
    ToolkitConfigEntry,
)
from noesium.noeagent.config import NoeConfig


class TestToolkitConfigEntry:
    """Test ToolkitConfigEntry with toolkit-specific fields."""

    def test_toolkit_config_entry_common_fields(self):
        """Test common toolkit config fields."""
        entry = ToolkitConfigEntry(timeout=300, shell="/bin/bash", max_output_length=10000)
        assert entry.timeout == 300
        assert entry.shell == "/bin/bash"
        assert entry.max_output_length == 10000

    def test_toolkit_config_entry_toolkit_specific_fields(self):
        """Test toolkit-specific config fields via extra='allow'."""
        # WizSearch-specific config
        entry = ToolkitConfigEntry(
            enabled_engines=["tavily", "brave"],
            max_results_per_engine=15,
            search_timeout=60,
            content_format="html",
        )
        assert entry.enabled_engines == ["tavily", "brave"]
        assert entry.max_results_per_engine == 15
        assert entry.search_timeout == 60
        assert entry.content_format == "html"

    def test_toolkit_config_entry_mixed_fields(self):
        """Test mixing common and toolkit-specific fields."""
        entry = ToolkitConfigEntry(
            timeout=600,  # Common field
            enabled_engines=["tavily"],  # Toolkit-specific field
        )
        assert entry.timeout == 600
        assert entry.enabled_engines == ["tavily"]

    def test_toolkit_config_entry_model_dump_excludes_common(self):
        """Test that model_dump can exclude common fields."""
        entry = ToolkitConfigEntry(
            timeout=300,
            shell="/bin/zsh",
            enabled_engines=["tavily"],
            max_results_per_engine=20,
        )
        # Exclude common fields to get only toolkit-specific config
        toolkit_specific = entry.model_dump(exclude_none=True, exclude={"timeout", "shell", "max_output_length"})
        assert toolkit_specific == {
            "enabled_engines": ["tavily"],
            "max_results_per_engine": 20,
        }


class TestToolkitConfigIntegration:
    """Test toolkit config integration with global config."""

    def test_global_config_with_toolkit_configs(self):
        """Test global config with toolkit-specific configurations."""
        config = FrameworkConfig()
        config.tools.toolkit_configs = {
            "web_search": ToolkitConfigEntry(
                enabled_engines=["tavily", "googleai"],
                max_results_per_engine=15,
                search_timeout=45,
            ),
            "bash": ToolkitConfigEntry(
                timeout=600,
                shell="/bin/zsh",
            ),
        }

        # Verify web_search config
        web_search_entry = config.tools.toolkit_configs["web_search"]
        assert web_search_entry.enabled_engines == ["tavily", "googleai"]
        assert web_search_entry.max_results_per_engine == 15
        assert web_search_entry.search_timeout == 45

        # Verify bash config
        bash_entry = config.tools.toolkit_configs["bash"]
        assert bash_entry.timeout == 600
        assert bash_entry.shell == "/bin/zsh"

    def test_noe_config_toolkit_configs_from_dict(self):
        """Test NoeConfig can receive toolkit_configs from dict."""
        noe_config = NoeConfig(
            toolkit_configs={
                "web_search": {
                    "enabled_engines": ["tavily"],
                    "max_results_per_engine": 20,
                },
                "bash": {
                    "timeout": 500,
                    "shell": "/bin/sh",
                },
            }
        )

        # Verify toolkit_configs are stored correctly
        assert "web_search" in noe_config.toolkit_configs
        assert noe_config.toolkit_configs["web_search"]["enabled_engines"] == ["tavily"]
        assert noe_config.toolkit_configs["web_search"]["max_results_per_engine"] == 20

        assert "bash" in noe_config.toolkit_configs
        assert noe_config.toolkit_configs["bash"]["timeout"] == 500
        assert noe_config.toolkit_configs["bash"]["shell"] == "/bin/sh"

    def test_toolkit_entry_model_dump_for_noe_config(self):
        """Test that ToolkitConfigEntry.model_dump works for NoeConfig extraction."""
        entry = ToolkitConfigEntry(
            timeout=300,  # Common field - should be excluded
            enabled_engines=["tavily"],  # Toolkit-specific - should be included
            max_results_per_engine=10,  # Toolkit-specific - should be included
        )

        # Simulate what NoeConfig.from_global_config does
        toolkit_specific = entry.model_dump(exclude_none=True, exclude={"timeout", "shell", "max_output_length"})

        # Common field should not be in the extracted config
        assert "timeout" not in toolkit_specific
        # Toolkit-specific fields should be present
        assert toolkit_specific["enabled_engines"] == ["tavily"]
        assert toolkit_specific["max_results_per_engine"] == 10


class TestWebSearchToolkitDefaultConfig:
    """Test WebSearch toolkit default configuration."""

    def test_web_search_default_uses_tavily(self):
        """Test that WebSearch toolkit uses Tavily as default search engine."""
        from noesium.core.toolify.config import ToolkitConfig
        from noesium.toolkits.web_search_toolkit import WebSearchToolkit

        # Create toolkit with default config
        config = ToolkitConfig(name="web_search", config={})
        toolkit = WebSearchToolkit(config)

        # Verify default uses Tavily
        assert toolkit.enabled_engines == ["tavily"]
        assert toolkit.max_results_per_engine == 10
        assert toolkit.search_timeout == 30
        assert toolkit.content_format == "markdown"

    def test_web_search_config_override(self):
        """Test that WebSearch toolkit can override defaults."""
        from noesium.core.toolify.config import ToolkitConfig
        from noesium.toolkits.web_search_toolkit import WebSearchToolkit

        # Create toolkit with custom config
        config = ToolkitConfig(
            name="web_search",
            config={
                "enabled_engines": ["tavily", "brave", "googleai"],
                "max_results_per_engine": 20,
                "search_timeout": 60,
                "content_format": "html",
            },
        )
        toolkit = WebSearchToolkit(config)

        # Verify custom config is applied
        assert toolkit.enabled_engines == ["tavily", "brave", "googleai"]
        assert toolkit.max_results_per_engine == 20
        assert toolkit.search_timeout == 60
        assert toolkit.content_format == "html"

    def test_web_search_partial_config_override(self):
        """Test that WebSearch toolkit can override some defaults while keeping others."""
        from noesium.core.toolify.config import ToolkitConfig
        from noesium.toolkits.web_search_toolkit import WebSearchToolkit

        # Create toolkit with partial custom config
        config = ToolkitConfig(
            name="web_search",
            config={
                "enabled_engines": ["duckduckgo", "brave"],
                # max_results_per_engine not specified, should use default
            },
        )
        toolkit = WebSearchToolkit(config)

        # Verify custom config for specified fields
        assert toolkit.enabled_engines == ["duckduckgo", "brave"]
        # Verify default for unspecified fields
        assert toolkit.max_results_per_engine == 10
        assert toolkit.search_timeout == 30
        assert toolkit.content_format == "markdown"
