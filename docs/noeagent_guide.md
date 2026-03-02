# NoeAgent User Guide

NoeAgent is an autonomous research assistant built on the Noesium framework. It supports two primary modes of operation: **Library Mode** (for programmatic use) and **TUI Mode** (for interactive terminal use).

## Table of Contents

- [NoeAgent User Guide](#noeagent-user-guide)
  - [Table of Contents](#table-of-contents)
  - [Quick Start](#quick-start)
    - [Library Mode](#library-mode)
    - [TUI Mode](#tui-mode)
  - [Modes of Operation](#modes-of-operation)
  - [Library Mode](#library-mode-1)
    - [Basic Usage](#basic-usage)
      - [Synchronous API](#synchronous-api)
      - [Asynchronous API](#asynchronous-api)
    - [Configuration](#configuration)
      - [Configuration Options](#configuration-options)
      - [Default Toolkits](#default-toolkits)
      - [Default Permissions](#default-permissions)
    - [Streaming Output](#streaming-output)
    - [Custom Tools](#custom-tools)
    - [MCP Server Integration](#mcp-server-integration)
  - [TUI Mode](#tui-mode-1)
    - [Running the TUI](#running-the-tui)
    - [TUI Commands](#tui-commands)
  - [Agent Modes](#agent-modes)
    - [Agent Mode](#agent-mode)
      - [Agent Mode Workflow](#agent-mode-workflow)
    - [Ask Mode](#ask-mode)
      - [Ask Mode Overrides](#ask-mode-overrides)
  - [Advanced Features](#advanced-features)
    - [Subagents](#subagents)
    - [Memory Providers](#memory-providers)
    - [Permissions](#permissions)
  - [Examples](#examples)
    - [Example 1: Simple Research Query](#example-1-simple-research-query)
    - [Example 2: File Analysis](#example-2-file-analysis)
    - [Example 3: Data Analysis](#example-3-data-analysis)
    - [Example 4: Streaming Research](#example-4-streaming-research)
    - [Example 5: Ask Mode for Memory Retrieval](#example-5-ask-mode-for-memory-retrieval)
    - [Example 6: Custom Research Workflow](#example-6-custom-research-workflow)
  - [Troubleshooting](#troubleshooting)
    - [Import Errors](#import-errors)
    - [Memory Provider Issues](#memory-provider-issues)
    - [LLM Provider Configuration](#llm-provider-configuration)

## Quick Start

### Installation

```bash
# Install dependencies
uv run pip install langchain-core langgraph
```

### Library Mode

```python
import asyncio
from noesium.agents.noe import NoeAgent

async def main():
    agent = NoeAgent()
    result = await agent.arun("What are the latest developments in quantum computing?")
    print(result)

asyncio.run(main())
```

### TUI Mode

```bash
# Run the interactive terminal UI
python -m noesium.agents.noe.tui
```

Or using the environment variable:

```bash
NOE_INTERFACE=tui python -m noesium.agents.noe.tui
```

## Modes of Operation

NoeAgent supports three interface modes (configured via `NoeConfig.interface_mode`):

| Mode | Description |
|------|-------------|
| `library` | Programmatic API use (default) |
| `tui` | Standalone interactive terminal UI |

**Exported Classes:**

The `noesium.agents.noe` module exports the following:

- `NoeAgent` - Main agent class
- `NoeConfig` - Configuration class
- `NoeMode` - Agent mode enum (`ASK` or `AGENT`)
- `TaskPlan` - Plan structure with steps
- `TaskStep` - Individual plan step
- `AgentAction` - Structured action schema
- `SubagentAction` - Subagent spawn/interact schema
- `ToolCallAction` - Tool invocation schema

| Mode | Description |
|------|-------------|
| `library` | Programmatic API use (default) |
| `tui` | Standalone interactive terminal UI |

## Library Mode

### Basic Usage

The `NoeAgent` class provides a simple API for autonomous research tasks.

#### Synchronous API

```python
from noesium.agents.noe import NoeAgent

agent = NoeAgent()
result = agent.run("Research the history of artificial intelligence")
print(result)
```

#### Asynchronous API

```python
import asyncio
from noesium.agents.noe import NoeAgent

async def main():
    agent = NoeAgent()
    result = await agent.arun("Analyze recent trends in renewable energy")
    print(result)

asyncio.run(main())
```

### Configuration

Create a custom configuration using `NoeConfig`:

```python
from noesium.agents.noe import NoeAgent, NoeConfig, NoeMode

config = NoeConfig(
    mode=NoeMode.AGENT,
    llm_provider="openrouter",
    model_name="anthropic/claude-3-5-sonnet",
    max_iterations=15,
    reflection_interval=3,
    enabled_toolkits=["wizsearch", "bash", "python_executor"],
    permissions=["fs:read", "net:outbound"],
)

agent = NoeAgent(config)
result = agent.run("Your research question")
```

#### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `mode` | `NoeMode` | `AGENT` | Agent mode (`AGENT` or `ASK`) |
| `llm_provider` | `str` | `"openrouter"` | LLM provider name |
| `model_name` | `str | None` | `None` | Specific model to use |
| `planning_model` | `str | None` | `None` | Model for task planning |
| `max_iterations` | `int` | `25` | Maximum execution iterations |
| `max_tool_calls_per_step` | `int` | `5` | Max tool calls per step |
| `reflection_interval` | `int` | `3` | Iterations between reflections |
| `enabled_toolkits` | `list[str]` | See defaults | Enabled toolkits |
| `mcp_servers` | `list[dict]` | `[]` | MCP server configurations |
| `custom_tools` | `list[Callable]` | `[]` | Custom tool functions |
| `memory_providers` | `list[str]` | `["working", "event_sourced", "memu"]` | Memory providers |
| `persist_memory` | `bool` | `True` | Persist research results |
| `working_directory` | `str | None` | `None` | Working directory for tools |
| `permissions` | `list[str]` | See defaults | Tool permissions |
| `enable_subagents` | `bool` | `True` | Enable subagent spawning |
| `subagent_max_depth` | `int` | `2` | Max subagent nesting depth |

#### Default Toolkits

The following toolkits are enabled by default in AGENT mode:

- `wizsearch` - Web search
- `jina_research` - Research via Jina
- `bash` - Shell command execution
- `python_executor` - Python code execution
- `file_edit` - File operations
- `memory` - Memory operations
- `document` - Document processing
- `image` - Image analysis
- `tabular_data` - Data table processing
- `video` - Video analysis
- `user_interaction` - User prompts

#### Default Permissions

Default permissions in AGENT mode:

- `fs:read` - File system read access
- `fs:write` - File system write access
- `net:outbound` - Network outbound access
- `shell:execute` - Shell command execution

### Streaming Output

For real-time progress updates, use the `stream()` method:

```python
import asyncio
from noesium.agents.noe import NoeAgent

async def main():
    agent = NoeAgent()
    async for chunk in agent.stream("Analyze Python async patterns"):
        print(chunk, end="", flush=True)
    print()  # New line after completion

asyncio.run(main())
```

For detailed event tracking, use the `astream_events()` method:

```python
import asyncio
from noesium.agents.noe import NoeAgent

async def main():
    agent = NoeAgent()

    async for event in agent.astream_events("Research AI trends"):
        event_type = event.get("type")

        if event_type == "plan_created":
            print(f"Plan created with {len(event['plan'].steps)} steps")

        elif event_type == "step_started":
            print(f"Starting step {event['index'] + 1}: {event['step']}")

        elif event_type == "tool_call_started":
            print(f"Calling tool: {event['name']}")

        elif event_type == "tool_call_completed":
            print(f"Tool completed: {event['name']}")

        elif event_type == "reflection":
            print(f"Reflecting: {event['text'][:100]}...")

        elif event_type == "final_answer":
            print(f"Answer: {event['text']}")

asyncio.run(main())
```

**Event Types:**

| Event Type | Description | Fields |
|------------|-------------|--------|
| `plan_created` | New task plan created | `plan: TaskPlan` |
| `step_started` | Plan step started | `step: str`, `index: int` |
| `tool_call_started` | Tool invocation started | `name: str`, `args: dict` |
| `tool_call_completed` | Tool execution finished | `name: str`, `result: str` |
| `thinking` | Agent reasoning/delegation | `thought: str` |
| `text_chunk` | Text output chunk | `text: str` |
| `reflection` | Agent self-assessment | `text: str` |
| `final_answer` | Final result | `text: str` |

### Custom Tools

Add custom Python functions as tools using the `custom_tools` configuration:

```python
from noesium.agents.noe import NoeAgent, NoeConfig

def calculate_fibonacci(n: int) -> dict:
    """Calculate the nth Fibonacci number."""
    if n <= 1:
        return {"result": n}
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return {"result": b}

def fetch_weather(city: str) -> dict:
    """Get weather information for a city."""
    # Your weather API logic here
    return {"city": city, "temperature": "72°F", "condition": "Sunny"}

config = NoeConfig(
    custom_tools=[calculate_fibonacci, fetch_weather]
)

agent = NoeAgent(config)
result = agent.run("What's the 20th Fibonacci number and the weather in Tokyo?")
```

### MCP Server Integration

Connect to Model Context Protocol (MCP) servers:

```python
from noesium.agents.noe import NoeAgent, NoeConfig

config = NoeConfig(
    mcp_servers=[
        {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed"],
        },
        {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_TOKEN": "your_token"},
        },
    ]
)

agent = NoeAgent(config)
```

## TUI Mode

### Running the TUI

The TUI provides a simple interactive terminal interface:

```python
from noesium.agents.noe import NoeAgent, NoeConfig, NoeMode

agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT, interface_mode="tui"))
agent.run_tui()
```

Or run as a module:

```bash
python -m noesium.agents.noe.tui
```

### TUI Commands

Once in TUI mode, you'll see the `noe>` prompt with a Rich-based interface:

```
╭─────────────────────────────────────────────────────────────╮
│ NoeAgent — Autonomous Research Assistant                    │
│ Mode: agent  |  Type /help for commands, /exit to quit.    │
╰─────────────────────────────────────────────────────────────╯

noe> What are the benefits of renewable energy?

[Agent response with live updates, tool panels, and plan table...]

noe> /exit
```

**Available Slash Commands:**

| Command | Action |
|---------|--------|
| `/exit`, `/quit` | Quit the TUI |
| `/help` | Show available commands |
| `/mode ask` | Switch to ask mode |
| `/mode agent` | Switch to agent mode |
| `/plan` | Show current task plan |
| `/memory` | Show memory stats |
| `/clear` | Clear the screen |
| Any text | Submit a research task to the agent |

**TUI Features:**

- **Live spinner** shows current activity (thinking, executing tools, etc.)
- **Collapsible tool-call panels** display tool arguments and results
- **Real-time plan table** updates as steps are completed
- **Reflection panels** show agent self-assessment
- **Multiline input** with backslash continuation
- **Markdown rendering** for final answers

## Agent Modes

NoeAgent operates in two distinct internal modes:

### Agent Mode

The full-featured autonomous research mode with:

- **Task Planning**: Breaks goals into actionable steps
- **Tool Execution**: Uses available tools to complete tasks
- **Reflection**: Periodically reviews progress and revises plans
- **Memory Persistence**: Stores research results for future reference

```python
from noesium.agents.noe import NoeAgent, NoeConfig, NoeMode

config = NoeConfig(mode=NoeMode.AGENT)
agent = NoeAgent(config)
```

#### Agent Mode Workflow

The agent follows a graph-based execution model with these nodes:

1. **plan**: Analyze goal and create step-by-step plan
2. **execute_step**: Decide next action (tool call, subagent, or text)
3. **tool_node**: Execute tool calls
4. **subagent_node**: Spawn/interact with subagents
5. **reflect**: Periodically assess progress
6. **revise_plan**: Update plan based on reflection
7. **finalize**: Synthesize results into final answer

**Routing logic:**

- After `execute_step`:
  - If tool calls pending → `tool_node`
  - If subagent action → `subagent_node`
  - If plan complete → `finalize`
  - If iteration limit reached → `finalize`
  - If reflection interval → `reflect`
  - Otherwise → `execute_step`

- After `reflect`:
  - If "REVISE" in reflection → `revise_plan`
  - If plan complete → `finalize`
  - Otherwise → `execute_step`

### Ask Mode

A simplified read-only Q&A mode:

- **No tools**: No web search, code execution, or file operations
- **Single iteration**: Direct answer based on knowledge and memory
- **Memory access**: Can retrieve previously stored information

```python
from noesium.agents.noe import NoeAgent, NoeConfig, NoeMode

config = NoeConfig(mode=NoeMode.ASK)
agent = NoeAgent(config)
result = agent.run("What did I research about quantum computing yesterday?")
```

#### Ask Mode Overrides

When using `NoeMode.ASK`, the following configuration is automatically applied:

- `max_iterations = 1`
- `enabled_toolkits = []`
- `permissions = []`
- `persist_memory = False`

## Advanced Features

### Subagents

NoeAgent can spawn child agents for parallel task execution:

```python
from noesium.agents.noe import NoeAgent, NoeConfig

config = NoeConfig(
    enable_subagents=True,
    subagent_max_depth=2,
)

agent = NoeAgent(config)
result = agent.run("Research both solar and wind energy advantages")
```

Subagents are automatically spawned when the LLM determines a task can be delegated.

### TaskPlan Structure

The `TaskPlan` class represents the agent's execution plan:

```python
from noesium.agents.noe import TaskPlan, TaskStep

# TaskPlan attributes
plan.goal: str                          # The research goal
plan.steps: list[TaskStep]              # List of plan steps
plan.current_step_index: int            # Index of current step
plan.is_complete: bool                  # Whether plan is finished

# Current step (None if complete)
current = plan.current_step

# Render as markdown
markdown = plan.to_todo_markdown()
```

**TaskStep attributes:**

```python
step.step_id: str                       # Unique identifier
step.description: str                   # Step description
step.status: str                        # "pending" | "in_progress" | "completed" | "failed"
step.result: str | None                 # Step result (if completed)
```

### Memory Providers

NoeAgent supports multiple memory providers:

| Provider | Description |
|----------|-------------|
| `working` | In-memory working storage |
| `event_sourced` | Event-based persistence |
| `memu` | Memu long-term memory |

```python
from noesium.agents.noe import NoeAgent, NoeConfig

config = NoeConfig(
    memory_providers=["working", "memu"],
    memu_memory_dir=".noe_memory",
    memu_user_id="my_user_id",
    persist_memory=True,
)

agent = NoeAgent(config)
```

### Permissions

Control what the agent can do with fine-grained permissions:

```python
from noesium.agents.noe import NoeAgent, NoeConfig

# Read-only agent
config = NoeConfig(
    permissions=["fs:read"],
)

# No network access
config = NoeConfig(
    permissions=["fs:read", "fs:write"],
)

# Full access
config = NoeConfig(
    permissions=["fs:read", "fs:write", "net:outbound", "shell:execute"],
)
```

## Examples

### Example 1: Simple Research Query

```python
from noesium.agents.noe import NoeAgent

agent = NoeAgent()
result = agent.run("What are the key differences between REST and GraphQL?")
print(result)
```

### Example 2: File Analysis

```python
from noesium.agents.noe import NoeAgent, NoeConfig

config = NoeConfig(
    permissions=["fs:read"],
    enabled_toolkits=["document", "file_edit"],
)

agent = NoeAgent(config)
result = agent.run("Analyze the contents of /path/to/report.pdf and summarize key findings")
```

### Example 3: Data Analysis

```python
from noesium.agents.noe import NoeAgent, NoeConfig

config = NoeConfig(
    enabled_toolkits=["python_executor", "tabular_data"],
)

agent = NoeAgent(config)
result = agent.run(
    "Load /data/sales.csv, calculate monthly totals, and identify the best performing month"
)
```

### Example 4: Streaming Research

```python
import asyncio
from noesium.agents.noe import NoeAgent

async def streaming_research():
    agent = NoeAgent()
    question = "What are the emerging trends in AI for 2024?"

    print(f"Researching: {question}\n")
    async for chunk in agent.stream(question):
        print(chunk, end="", flush=True)
    print("\n\nDone!")

asyncio.run(streaming_research())
```

### Example 5: Ask Mode for Memory Retrieval

```python
from noesium.agents.noe import NoeAgent, NoeConfig, NoeMode

# First, do some research with memory enabled
agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT, persist_memory=True))
agent.run("Research the history of the Roman Empire")

# Later, retrieve what was learned
ask_agent = NoeAgent(NoeConfig(mode=NoeMode.ASK))
answer = ask_agent.run("What did I learn about the Roman Empire?")
print(answer)
```

### Example 6: Custom Research Workflow

```python
from noesium.agents.noe import NoeAgent, NoeConfig

def search_arxiv(query: str) -> dict:
    """Search arXiv for papers matching the query."""
    import requests
    url = f"http://export.arxiv.org/api/query?search_query=all:{query}"
    response = requests.get(url)
    return {"papers": response.text[:500]}  # Truncated example

config = NoeConfig(
    custom_tools=[search_arxiv],
    enabled_toolkits=["python_executor", "document"],
)

agent = NoeAgent(config)
result = agent.run("Find recent papers about transformer architectures and summarize them")
```

## Troubleshooting

### Import Errors

If you see import errors:

```bash
# Install required dependencies
uv run pip install langchain-core langgraph
```

### Memory Provider Issues

If memu fails to initialize, it will log a warning but continue with other providers:

```
WARNING: Failed to initialize memu provider: ...
```

### LLM Provider Configuration

Make sure your LLM provider credentials are configured. The default is OpenRouter:

```bash
export OPENROUTER_API_KEY="your_key"
```
