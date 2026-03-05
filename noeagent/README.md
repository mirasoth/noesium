# NoeAgent

Autonomous research assistant with dual modes (Ask/Agent) built on the Noesium framework.

## Features

- **Interactive TUI**: Rich terminal user interface with progress display and real-time updates
- **Dual-Mode Operation**:
  - **Ask Mode**: Conversational assistant for quick questions and guidance
  - **Agent Mode**: Autonomous agent with task planning and execution
- **Built-in Task Planning**: Automatically breaks down complex tasks into manageable steps
- **Subagent Coordination**: Orchestrates specialized subagents for different tasks
- **Multi-Provider Support**: Works with OpenAI, Anthropic, Google, and local LLMs

## Installation

```bash
# Using pip
pip install noeagent

# Using uv (recommended)
uv pip install noeagent

# With all optional dependencies
pip install noeagent[all]
```

## Quick Start

### Library Mode

```python
from noeagent import NoeAgent

# Initialize agent
agent = NoeAgent(
    model="gpt-4",
    mode="agent"
)

# Run a task
result = await agent.run("Research the latest advances in quantum computing")
print(result)
```

### TUI Mode

```bash
# Start interactive TUI
noeagent

# Start in Ask mode
noeagent --mode ask

# Start with specific model
noeagent --model gpt-4 --mode agent
```

## Configuration

NoeAgent uses the Noesium configuration system. Create a `.env` file in your working directory:

```bash
# LLM Provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Or use Anthropic
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Or use local models
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

### Configuration File

Create `noesium.toml` for advanced configuration:

```toml
[llm]
provider = "openai"
model = "gpt-4"
temperature = 0.7

[agent]
mode = "agent"
max_iterations = 10
enable_subagents = true

[memory]
provider = "ephemeral"  # or "memu" for persistent memory
```

## Architecture

NoeAgent is built on the Noesium framework and leverages:

- **LangGraph**: For agent workflow orchestration
- **Rich**: For terminal UI rendering
- **Noesium Core**: Memory, tools, and subagent management

```
┌─────────────────────────────────────────┐
│            NoeAgent TUI                 │
│  ┌─────────────────────────────────┐   │
│  │   Ask Mode   │   Agent Mode     │   │
│  └─────────────────────────────────┘   │
│              ↓                          │
│  ┌─────────────────────────────────┐   │
│  │      Task Planner               │   │
│  └─────────────────────────────────┘   │
│              ↓                          │
│  ┌─────────────────────────────────┐   │
│  │   Noesium Framework Core        │   │
│  │  - Memory Management            │   │
│  │  - Tool Execution               │   │
│  │  - Subagent Orchestration       │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## Documentation

- [User Guide](../docs/noeagent_guide.md) - Comprehensive usage documentation
- [Configuration Guide](../docs/toolkit_configuration_guide.md) - Detailed configuration options
- [Developer Guide](../docs/dev_guide.md) - Framework development guide

## Examples

See the [examples/noeagent/](../examples/noeagent/) directory for usage examples.

## Requirements

- Python >= 3.11
- OpenAI API key (or other LLM provider)

## License

MIT License - see [LICENSE](../LICENSE) for details.

## Related Projects

- [Noesium](../noesium/) - Core cognitive agentic framework
- [Voyager](../voyager/) - Web-based coding assistant

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines.