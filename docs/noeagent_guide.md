# NoeAgent User Guide

NoeAgent is an autonomous research assistant built on the Noesium framework. It supports two primary modes of operation: **Library Mode** (for programmatic use) and **TUI Mode** (for interactive terminal use).

## Table of Contents

- [NoeAgent User Guide](#noeagent-user-guide)
  - [Table of Contents](#table-of-contents)
  - [Quick Start](#quick-start)
    - [Installation](#installation)
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
      - [`astream_progress()` — Canonical Typed Event Stream](#astream_progress--canonical-typed-event-stream)
      - [`astream_events()` — Dict-Based Event Stream](#astream_events--dict-based-event-stream)
      - [ProgressEvent Fields](#progressevent-fields)
      - [ProgressEventType Values](#progresseventtype-values)
      - [ProgressCallback Protocol](#progresscallback-protocol)
      - [SessionLogger](#sessionlogger)
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
      - [In-Process Subagents](#in-process-subagents)
      - [External CLI Subagent Daemons](#external-cli-subagent-daemons)
      - [Browser Use Subagent Example](#browser-use-subagent-example)
    - [TaskPlan Structure](#taskplan-structure)
    - [Memory Providers](#memory-providers)
    - [Permissions](#permissions)
  - [Examples](#examples)
    - [Example 1: Simple Research Query](#example-1-simple-research-query)
    - [Example 2: File Analysis](#example-2-file-analysis)
    - [Example 3: Data Analysis](#example-3-data-analysis)
    - [Example 4: Streaming Research](#example-4-streaming-research)
    - [Example 5: Ask Mode for Memory Retrieval](#example-5-ask-mode-for-memory-retrieval)
    - [Example 6: Custom Research Workflow](#example-6-custom-research-workflow)
    - [Example 7: Subagent Configuration](#example-7-subagent-configuration)
    - [Example 8: Browser Automation with Subagent](#example-8-browser-automation-with-subagent)
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
from noesium.noeagent import NoeAgent

async def main():
    agent = NoeAgent()
    result = await agent.arun("What are the latest developments in quantum computing?")
    print(result)

asyncio.run(main())
```

### TUI Mode

```bash
# Run the interactive terminal UI
python -m noesium.noeagent.tui
```

Or using the environment variable:

```bash
uv run python -m noesium.noeagent.tui
```

## Modes of Operation

NoeAgent supports three interface modes (configured via `NoeConfig.interface_mode`):

| Mode | Description |
|------|-------------|
| `library` | Programmatic API use (default) |
| `tui` | Standalone interactive terminal UI |

**Exported Classes:**

The `noesium.noeagent` module exports the following:

- `NoeAgent` - Main agent class
- `NoeConfig` - Configuration class
- `NoeMode` - Agent mode enum (`ASK` or `AGENT`)
- `AgentSubagentConfig` - Built-in agent subagent configuration (browser_use, tacitus, etc.)
- `CliSubagentConfig` - External CLI subagent daemon configuration
- `TaskPlan` - Plan structure with steps
- `TaskStep` - Individual plan step
- `AgentAction` - Structured action schema (with mutual exclusivity validator)
- `SubagentAction` - Subagent spawn/interact/CLI schema
- `ToolCallAction` - Tool invocation schema
- `ProgressEvent` - Typed progress event model
- `ProgressEventType` - Enumeration of all progress event kinds
- `ProgressCallback` - Push-style callback protocol for consumers
- `SessionLogger` - JSONL session logger

| Mode | Description |
|------|-------------|
| `library` | Programmatic API use (default) |
| `tui` | Standalone interactive terminal UI |

## Library Mode

### Basic Usage

The `NoeAgent` class provides a simple API for autonomous research tasks.

#### Synchronous API

```python
from noesium.noeagent import NoeAgent

agent = NoeAgent()
result = agent.run("Research the history of artificial intelligence")
print(result)
```

#### Asynchronous API

```python
import asyncio
from noesium.noeagent import NoeAgent

async def main():
    agent = NoeAgent()
    result = await agent.arun("Analyze recent trends in renewable energy")
    print(result)

asyncio.run(main())
```

### Configuration

Create a custom configuration using `NoeConfig`:

```python
from noesium.noeagent import NoeAgent, NoeConfig, NoeMode

config = NoeConfig(
    mode=NoeMode.AGENT,
    llm_provider="openai",
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
| `llm_provider` | `str` | `"openai"` | LLM provider name |
| `model_name` | `str \| None` | `None` | Specific model to use |
| `planning_model` | `str \| None` | `None` | Separate model for task planning |
| `max_iterations` | `int` | `25` | Maximum execution iterations |
| `max_tool_calls_per_step` | `int` | `5` | Max tool calls per step (enforced by truncation) |
| `reflection_interval` | `int` | `3` | Iterations between reflections |
| `interface_mode` | `str` | `"library"` | `"library"` or `"tui"` |
| `progress_callbacks` | `list[Callable]` | `[]` | Push-style ProgressCallback instances |
| `session_log_dir` | `str` | `"~/.noeagent/sessions"` | JSONL session log directory |
| `enable_session_logging` | `bool` | `True` | Enable JSONL session logging |
| `enabled_toolkits` | `list[str]` | All 18 toolkits | Enabled toolkits |
| `mcp_servers` | `list[dict]` | `[]` | MCP server configurations |
| `custom_tools` | `list[Callable]` | `[]` | Custom tool functions |
| `memory_providers` | `list[str]` | `["working", "event_sourced", "memu"]` | Memory providers |
| `persist_memory` | `bool` | `True` | Persist research results |
| `working_directory` | `str \| None` | `None` | Working directory for tools |
| `permissions` | `list[str]` | See defaults | Tool permissions |
| `enable_subagents` | `bool` | `True` | Enable in-process subagent spawning |
| `subagent_max_depth` | `int` | `2` | Max subagent nesting depth |
| `agent_subagents` | `list[AgentSubagentConfig]` | See defaults | Built-in agent subagent configurations |
| `cli_subagents` | `list[CliSubagentConfig]` | `[]` | External CLI subagent daemon configurations |

#### Default Toolkits

All 18 registered toolkits are enabled by default in AGENT mode:

- `wizsearch` - Multi-engine web search
- `jina_research` - Research via Jina Reader
- `bash` - Shell command execution
- `python_executor` - Python code execution
- `file_edit` - File operations
- `memory` - Memory operations
- `document` - Document processing (PDF, Word, etc.)
- `image` - Image processing and generation
- `tabular_data` - CSV/Excel data processing
- `video` - Video processing
- `user_interaction` - User prompts
- `arxiv` - ArXiv paper search and retrieval
- `serper` - Google search via Serper API
- `wikipedia` - Wikipedia search and retrieval
- `github` - GitHub API operations
- `gmail` - Gmail email operations
- `audio` - General audio processing
- `audio_aliyun` - Aliyun audio processing (TTS, STT)

#### Default Permissions

Default permissions in AGENT mode:

- `fs:read` - File system read access
- `fs:write` - File system write access
- `net:outbound` - Network outbound access
- `shell:execute` - Shell command execution

### Streaming Output

For real-time progress updates, use the `stream()` method (yields final answer text only):

```python
import asyncio
from noesium.noeagent import NoeAgent

async def main():
    agent = NoeAgent()
    async for chunk in agent.stream("Analyze Python async patterns"):
        print(chunk, end="", flush=True)
    print()

asyncio.run(main())
```

#### `astream_progress()` — Canonical Typed Event Stream

The primary streaming API. Yields `ProgressEvent` objects with full typing:

```python
import asyncio
from noesium.noeagent import NoeAgent, ProgressEventType

async def main():
    agent = NoeAgent()

    async for event in agent.astream_progress("Research AI trends"):
        if event.type == ProgressEventType.PLAN_CREATED:
            print(f"Plan: {event.summary}")

        elif event.type == ProgressEventType.STEP_START:
            print(f"Step {event.step_index + 1}: {event.step_desc}")

        elif event.type == ProgressEventType.TOOL_START:
            print(f"Using {event.tool_name}({event.tool_args})")

        elif event.type == ProgressEventType.TOOL_END:
            print(f"Result: {event.tool_result}")

        elif event.type == ProgressEventType.SUBAGENT_START:
            print(f"Delegating to [{event.subagent_id}]")

        elif event.type == ProgressEventType.REFLECTION:
            print(f"Reflecting: {event.text[:100]}...")

        elif event.type == ProgressEventType.FINAL_ANSWER:
            print(f"Answer: {event.text}")

asyncio.run(main())
```

#### `astream_events()` — Dict-Based Event Stream

Backward-compatible wrapper that converts each `ProgressEvent` to a plain dict:

```python
async for event in agent.astream_events("Research AI trends"):
    if event["type"] == "plan.created":
        print(event["summary"])
```

#### ProgressEvent Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | `ProgressEventType` | Event kind (see table below) |
| `timestamp` | `datetime` | UTC timestamp |
| `session_id` | `str` | Session identifier |
| `sequence` | `int` | Monotonic sequence number |
| `node` | `str \| None` | Graph node that emitted the event |
| `step_index` | `int \| None` | Current plan step index |
| `step_desc` | `str \| None` | Current plan step description |
| `tool_name` | `str \| None` | Tool name (for TOOL_START/TOOL_END) |
| `tool_args` | `dict \| None` | Tool arguments (for TOOL_START) |
| `tool_result` | `str \| None` | Tool result summary (for TOOL_END) |
| `subagent_id` | `str \| None` | Subagent identifier |
| `text` | `str \| None` | Text content (for TEXT_CHUNK, FINAL_ANSWER) |
| `summary` | `str \| None` | Short one-liner suitable for TUI rendering |
| `detail` | `str \| None` | Verbose content for session logging |
| `plan_snapshot` | `dict \| None` | Full plan dump (for PLAN_CREATED/PLAN_REVISED) |
| `error` | `str \| None` | Error message (for ERROR events) |
| `metadata` | `dict` | Arbitrary extension metadata |

#### ProgressEventType Values

| Event Type | Value | Description |
|------------|-------|-------------|
| `SESSION_START` | `session.start` | Session initiated |
| `SESSION_END` | `session.end` | Session completed |
| `PLAN_CREATED` | `plan.created` | New task plan created |
| `PLAN_REVISED` | `plan.revised` | Plan updated after reflection |
| `STEP_START` | `step.start` | Plan step execution started |
| `STEP_COMPLETE` | `step.complete` | Plan step finished |
| `TOOL_START` | `tool.start` | Tool invocation started |
| `TOOL_END` | `tool.end` | Tool execution finished |
| `SUBAGENT_START` | `subagent.start` | Subagent spawned/messaged |
| `SUBAGENT_PROGRESS` | `subagent.progress` | Subagent intermediate update |
| `SUBAGENT_END` | `subagent.end` | Subagent task completed |
| `THINKING` | `thinking` | Agent reasoning |
| `TEXT_CHUNK` | `text.chunk` | Text output chunk |
| `PARTIAL_RESULT` | `partial.result` | Intermediate result |
| `REFLECTION` | `reflection` | Agent self-assessment |
| `FINAL_ANSWER` | `final.answer` | Final synthesized result |
| `ERROR` | `error` | Error occurred |

#### ProgressCallback Protocol

Library consumers can register push-style callbacks:

```python
from noesium.noeagent import NoeAgent, NoeConfig, ProgressEvent, ProgressCallback

class MyCallback:
    async def on_progress(self, event: ProgressEvent) -> None:
        print(f"[{event.type.value}] {event.summary}")

config = NoeConfig(progress_callbacks=[MyCallback()])
agent = NoeAgent(config)
await agent.arun("Research quantum computing")
```

#### SessionLogger

JSONL-based session logging that persists all progress events to disk:

```python
from noesium.noeagent import NoeConfig

config = NoeConfig(
    enable_session_logging=True,
    session_log_dir="~/.noeagent/sessions",
)
```

Session logs are written as `.jsonl` files in the configured directory, one JSON object per line corresponding to each `ProgressEvent`.

### Custom Tools

Add custom Python functions as tools using the `custom_tools` configuration:

```python
from noesium.noeagent import NoeAgent, NoeConfig

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
from noesium.noeagent import NoeAgent, NoeConfig

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
from noesium.noeagent import NoeAgent, NoeConfig, NoeMode

agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT, interface_mode="tui"))
agent.run_tui()
```

Or run as a module:

```bash
python -m noesium.noeagent.tui
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
| `/session` | Show current session ID and log path |
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
from noesium.noeagent import NoeAgent, NoeConfig, NoeMode

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
from noesium.noeagent import NoeAgent, NoeConfig, NoeMode

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

NoeAgent supports two categories of child agents:

#### In-Process Subagents

Child `NoeAgent` instances spawned within the same process. The LLM decides when to delegate via the `SubagentAction` schema:

```python
from noesium.noeagent import NoeAgent, NoeConfig

config = NoeConfig(
    enable_subagents=True,
    subagent_max_depth=2,
)

agent = NoeAgent(config)
result = agent.run("Research both solar and wind energy advantages")
```

**Built-in Agent Subagents:**

NoeAgent comes with pre-configured agent subagents for specialized tasks:

- **browser_use**: Web automation agent for browser interaction and DOM manipulation
- **tacitus**: Research agent with iterative query generation and web search

These are enabled by default and can be customized via `config.builtin`:

```python
from noesium.noeagent import NoeAgent, NoeConfig, AgentSubagentConfig

config = NoeConfig(
    enable_subagents=True,
    builtin=[
        AgentSubagentConfig(
            name="browser_use",
            agent_type="browser_use",
            description="Web automation agent for browser interaction",
            enabled=True,
        ),
        AgentSubagentConfig(
            name="tacitus",
            agent_type="tacitus",
            description="Research agent with iterative query generation",
            enabled=True,
        ),
    ],
)

agent = NoeAgent(config)
```

To disable specific built-in subagents, set `enabled=False` or remove them from the list.

#### External CLI Subagent Daemons

Long-lived external CLI processes (e.g., Claude Code CLI) that run as persistent daemons. Configured via `CliSubagentConfig`:

```python
from noesium.noeagent import NoeAgent, NoeConfig, CliSubagentConfig

config = NoeConfig(
    external=[
        CliSubagentConfig(
            name="claude-code",
            command="claude",
            args=["--session"],
            timeout=300,
            restart_policy="on-failure",
            task_types=["code_generation", "code_review"],
        ),
    ],
)

agent = NoeAgent(config)
```

The `SubagentAction` schema supports five actions for routing:

| Action | Target | Description |
|--------|--------|-------------|
| `spawn` | In-process | Create a new child NoeAgent |
| `interact` | In-process | Send a message to an existing child |
| `spawn_cli` | CLI daemon | Start an external CLI subagent |
| `interact_cli` | CLI daemon | Send a task to a running CLI daemon |
| `terminate_cli` | CLI daemon | Shut down a CLI daemon |

The LLM intelligently determines whether to use a tool, an in-process subagent, or a CLI subagent based on task complexity, required autonomy, and configured `task_types`.

#### Browser Use Subagent Example

The `browser_use` subagent is ideal for web automation tasks. Here's how to use it:

```python
from noesium.noeagent import NoeAgent, NoeConfig

# Enable browser_use subagent (enabled by default)
config = NoeConfig(
    enable_subagents=True,
    subagent_max_depth=2,
)

agent = NoeAgent(config)

# The agent will automatically delegate browser tasks to the browser_use subagent
result = agent.run(
    "Navigate to example.com, fill out the contact form with test data, "
    "and screenshot the confirmation page"
)
```

**When the LLM uses browser_use:**
- Web scraping and data extraction
- Form filling and submission
- Multi-page navigation workflows
- Screenshot capture and visual verification
- DOM manipulation and testing

The browser_use subagent operates autonomously and returns results back to the parent agent for synthesis.

### TaskPlan Structure

The `TaskPlan` class represents the agent's execution plan:

```python
from noesium.noeagent import TaskPlan, TaskStep

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
step.execution_hint: str                # "tool" | "subagent" | "cli_subagent" | "auto"
```

The `execution_hint` guides the planner's routing heuristic. When set to `"auto"` (default), the LLM decides the execution strategy at runtime.

### Memory Providers

NoeAgent supports multiple memory providers:

| Provider | Description |
|----------|-------------|
| `working` | In-memory working storage |
| `event_sourced` | Event-based persistence |
| `memu` | Memu long-term memory |

```python
from noesium.noeagent import NoeAgent, NoeConfig

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
from noesium.noeagent import NoeAgent, NoeConfig

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
from noesium.noeagent import NoeAgent

agent = NoeAgent()
result = agent.run("What are the key differences between REST and GraphQL?")
print(result)
```

### Example 2: File Analysis

```python
from noesium.noeagent import NoeAgent, NoeConfig

config = NoeConfig(
    permissions=["fs:read"],
    enabled_toolkits=["document", "file_edit"],
)

agent = NoeAgent(config)
result = agent.run("Analyze the contents of /path/to/report.pdf and summarize key findings")
```

### Example 3: Data Analysis

```python
from noesium.noeagent import NoeAgent, NoeConfig

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
from noesium.noeagent import NoeAgent

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
from noesium.noeagent import NoeAgent, NoeConfig, NoeMode

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
from noesium.noeagent import NoeAgent, NoeConfig

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

### Example 7: Subagent Configuration

```python
from noesium.noeagent import (
    NoeAgent,
    NoeConfig,
    AgentSubagentConfig,
    CliSubagentConfig,
)

# Configure with both agent subagents and CLI subagents
config = NoeConfig(
    enable_subagents=True,
    subagent_max_depth=2,
    # Built-in agent subagents (browser_use, tacitus)
    agent_subagents=[
        AgentSubagentConfig(
            name="browser_use",
            agent_type="browser_use",
            description="Web automation agent for browser tasks",
            enabled=True,
        ),
        AgentSubagentConfig(
            name="tacitus",
            agent_type="tacitus",
            description="Deep research agent with iterative search",
            enabled=True,
        ),
    ],
    # External CLI subagents
    cli_subagents=[
        CliSubagentConfig(
            name="claude-code",
            command="claude",
            args=["--session"],
            timeout=300,
            task_types=["code_generation", "code_review"],
        ),
    ],
)

agent = NoeAgent(config)
result = agent.run(
    "Research the latest React patterns, then generate a component example"
)
```

### Example 8: Browser Automation with Subagent

```python
from noesium.noeagent import NoeAgent, NoeConfig

# Browser automation is enabled by default via browser_use subagent
agent = NoeAgent(NoeConfig(enable_subagents=True))

result = agent.run(
    "Go to github.com/trending, scrape the top 5 repositories, "
    "and summarize what makes them popular"
)

# The agent will:
# 1. Delegate browser navigation to browser_use subagent
# 2. Subagent scrapes the page and extracts data
# 3. Parent agent synthesizes findings into summary
print(result)
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

Make sure your LLM provider credentials are configured. The default provider is OpenAI (set via `NOE_LLM_PROVIDER` env var):

```bash
export NOE_LLM_PROVIDER="openai"
export OPENAI_API_KEY="your_key"
```
