# Toolkit Configuration Guide

## Overview

NoeAgent supports toolkit-specific configuration through the `toolkit_configs` field in both global configuration (`~/.noeagent/config.json`) and programmatic configuration. This allows fine-grained control over each toolkit's behavior.

## Configuration Architecture

### 1. Global Configuration Structure

The global configuration file (`~/.noeagent/config.json`) supports toolkit-specific settings:

```json
{
  "tools": {
    "enabled_toolkits": ["bash", "web_search", "file_edit", ...],
    "toolkit_configs": {
      "web_search": {
        "enabled_engines": ["tavily"],
        "max_results_per_engine": 10,
        "search_timeout": 30,
        "content_format": "markdown"
      },
      "bash": {
        "timeout": 600,
        "shell": "/bin/bash"
      }
    }
  }
}
```

### 2. ToolkitConfigEntry Model

The `ToolkitConfigEntry` model supports two types of fields:

**Common Fields** (applicable to most toolkits):
- `timeout`: Timeout in seconds for toolkit operations
- `shell`: Shell to use (for bash toolkit)
- `max_output_length`: Maximum output length

**Toolkit-Specific Fields** (via Pydantic's `extra="allow"`):
- Any additional fields specific to a toolkit
- Passed directly to the toolkit's configuration

### 3. Configuration Flow

```
Global Config (config.json)
  └─> tools.toolkit_configs (Dict[str, ToolkitConfigEntry])
       └─> NoeConfig.from_global_config()
            └─> Extracts toolkit-specific fields (excludes common fields)
                 └─> NoeConfig.toolkit_configs (Dict[str, Dict[str, Any]])
                      └─> Agent._setup_capabilities()
                           └─> Merges with session-specific config
                                └─> ToolkitConfig.config
                                     └─> Toolkit.__init__()
```

## Usage Examples

### Example 1: Configure WebSearch to Use Tavily (Default)

**Global config (`~/.noeagent/config.json`):**
```json
{
  "tools": {
    "enabled_toolkits": ["web_search"],
    "toolkit_configs": {
      "web_search": {
        "enabled_engines": ["tavily"],
        "max_results_per_engine": 10,
        "search_timeout": 30,
        "content_format": "markdown"
      }
    }
  }
}
```

**Programmatic usage:**
```python
from noesium.noeagent import NoeAgent
from noesium.noeagent.config import NoeConfig

# Via global config
agent = NoeAgent()

# Or programmatically
config = NoeConfig(
    enabled_toolkits=["web_search"],
    toolkit_configs={
        "web_search": {
            "enabled_engines": ["tavily", "brave"],
            "max_results_per_engine": 20,
        }
    }
)
agent = NoeAgent(config=config)
```

### Example 2: Configure Bash Toolkit

```json
{
  "tools": {
    "toolkit_configs": {
      "bash": {
        "timeout": 600,
        "shell": "/bin/zsh",
        "max_output_length": 50000
      }
    }
  }
}
```

### Example 3: Use Multiple Search Engines

```json
{
  "tools": {
    "toolkit_configs": {
      "web_search": {
        "enabled_engines": ["tavily", "brave", "googleai"],
        "max_results_per_engine": 15,
        "search_timeout": 45,
        "content_format": "html"
      }
    }
  }
}
```

## WebSearch Configuration Options

The WebSearch toolkit supports the following configuration fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled_engines` | `List[str]` | `["tavily"]` | List of search engines to use. Available: `tavily`, `duckduckgo`, `brave`, `bing`, `google`, `googleai`, `searxng`, `baidu`, `wechat` |
| `max_results_per_engine` | `int` | `10` | Maximum results per search engine |
| `search_timeout` | `int` | `30` | Search timeout in seconds |
| `content_format` | `str` | `"markdown"` | Output format for crawled content: `"markdown"`, `"html"`, or `"text"` |

### Default Configuration

WebSearch now uses **Tavily** as the default search engine, providing:
- AI-powered search summaries
- High-quality, relevant results
- Advanced search depth options

To override the default and use multiple engines:

```json
{
  "tools": {
    "toolkit_configs": {
      "web_search": {
        "enabled_engines": ["tavily", "duckduckgo", "brave"]
      }
    }
  }
}
```

## Common Toolkit Configuration Fields

These fields are shared across multiple toolkits:

| Field | Type | Description | Applicable Toolkits |
|-------|------|-------------|---------------------|
| `timeout` | `int` | Operation timeout in seconds | bash, python_executor, etc. |
| `shell` | `str` | Shell executable path | bash |
| `max_output_length` | `int` | Maximum output length | bash, python_executor |

## Implementation Details

### How Toolkit Configs Are Applied

1. **Global Config Loading**:
   - `NoeAgentConfig` is loaded from `~/.noeagent/config.json`
   - `ToolkitConfigEntry` instances store toolkit-specific settings

2. **NoeConfig Extraction**:
   - `NoeConfig.from_global_config()` extracts toolkit-specific fields
   - Common fields are excluded to keep only toolkit-relevant settings
   - Result stored in `NoeConfig.toolkit_configs` as `Dict[str, Dict[str, Any]]`

3. **Agent Initialization**:
   - `NoeAgent._setup_capabilities()` loads each toolkit
   - Session-specific config (workspace paths, etc.) is added
   - `toolkit_configs` from NoeConfig are merged on top
   - Final config passed to toolkit via `ToolkitConfig.config`

4. **Toolkit Initialization**:
   - Each toolkit reads from `self.config.config.get(field_name, default)`
   - Defaults are applied for missing fields

### Key Code Locations

- **ToolkitConfigEntry Model**: `noesium/core/config.py:110`
- **NoeConfig.toolkit_configs**: `noesium/noeagent/config.py:180-185`
- **Config Extraction**: `noesium/noeagent/config.py:313-316`
- **Config Merging**: `noesium/noeagent/agent.py:250-261`
- **WebSearch Defaults**: `noesium/toolkits/web_search_toolkit.py:66-69`

## Migration Guide

### From Old Configuration

**Before** (toolkit configs were ignored):
```json
{
  "tools": {
    "toolkit_configs": {}  // Not used
  }
}
```

**After** (toolkit configs are now active):
```json
{
  "tools": {
    "toolkit_configs": {
      "web_search": {
        "enabled_engines": ["tavily"]
      }
    }
  }
}
```

### Default Search Engine Change

**Before**: WebSearch defaulted to `["tavily", "duckduckgo"]`

**After**: WebSearch defaults to `["tavily"]`

To restore old behavior:
```json
{
  "tools": {
    "toolkit_configs": {
      "web_search": {
        "enabled_engines": ["tavily", "duckduckgo"]
      }
    }
  }
}
```

## Testing

Run the toolkit configuration tests:

```bash
python -m pytest tests/toolkits/test_toolkit_config_integration.py -v
```

All tests should pass, verifying:
- ToolkitConfigEntry supports both common and toolkit-specific fields
- Global config properly stores toolkit configurations
- NoeConfig correctly extracts toolkit-specific settings
- WizSearch toolkit uses Tavily as default
- Toolkit configurations can be overridden

## Summary

The toolkit configuration system provides:

✅ **Flexible Configuration**: Each toolkit can have its own settings
✅ **Type Safety**: Pydantic models ensure type correctness
✅ **Default Values**: Sensible defaults when config is not specified
✅ **Override Support**: Users can override any toolkit setting
✅ **Tavily Default**: WizSearch uses Tavily search by default for better results

For more information, see:
- `noesium/noeagent/example_config.json` for example configurations
- `tests/toolkits/test_toolkit_config_integration.py` for test examples
- Individual toolkit documentation for available configuration options