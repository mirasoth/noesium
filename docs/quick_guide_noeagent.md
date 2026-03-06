# NoeAgent Quick Guide

**NoeAgent** is an autonomous research assistant with dual modes (Ask/Agent) built on the Noesium framework. It demonstrates advanced multi-agent orchestration patterns.

## Installation

```bash
# From PyPI
pip install noeagent

# With all dependencies
pip install noeagent[all]
```

## Quick Start

### TUI Mode

```bash
# Start interactive TUI
noeagent

# Start in specific mode
noeagent --mode ask
noeagent --mode agent

# Specify model
noeagent --model gpt-4o
```

### Library Mode

```python
from noeagent import NoeAgent

# Agent mode
agent = NoeAgent(mode="agent")
result = await agent.run("Research quantum computing advances")

# Ask mode
agent_ask = NoeAgent(mode="ask")
answer = await agent_ask.run("What is machine learning?")
```

## Usage Modes

### Ask Mode

**Purpose**: Quick Q&A and conversational assistance

- Single iteration
- No tool execution
- Immediate responses

```python
agent = NoeAgent(mode="ask")
response = await agent.run("Explain transformer architectures")
```

### Agent Mode

**Purpose**: Complex task execution with planning and tools

- Multi-step planning
- Tool execution
- Subagent coordination
- Progress tracking

```python
agent = NoeAgent(
    mode="agent",
    max_iterations=25,
    enabled_toolkits=["bash", "search", "python_executor"]
)

result = await agent.run(
    "Research and summarize the latest papers on transformers"
)
```

## Configuration

### Environment Variables

```bash
export NOESIUM_LLM_PROVIDER="openai"
export OPENAI_API_KEY="sk-..."
export SERPER_API_KEY="..."  # For web search
```

### Configuration File

Create \`noesium.toml\`:

```toml
[llm]
provider = "openai"
model = "gpt-4o"

[agent]
mode = "agent"
max_iterations = 25

[tools]
enabled_toolkits = ["bash", "search", "python_executor"]
```

## Features

### Interactive TUI

Rich terminal interface with:
- Progress tracking
- Task plan visualization
- Tool execution logs
- Subagent coordination view

### Task Planning

Automatic task decomposition:

```python
agent = NoeAgent(mode="agent")
result = await agent.run("Create a Python web scraper")
# Automatically plans and executes steps
```

### Subagent Coordination

Delegate to specialized subagents:

```python
result = await agent.run("""
Research REST API best practices
and create an example implementation
""")
# Spawns researcher and coder subagents
```

## CLI Reference

```bash
noeagent                          # Start TUI
noeagent --mode ask               # Ask mode
noeagent --mode agent             # Agent mode
noeagent --model gpt-4o           # Specify model
noeagent --max-iterations 20      # Set limits
noeagent config init openai       # Initialize config
noeagent config show              # Show config
```

## Next Steps

- **[Noesium Guide](quick_guide_noesium.md)**: Learn the framework
- **[Voyager Guide](quick_guide_voyager.md)**: 24/7 companion app
- **[Examples](../examples/)**: Usage examples
