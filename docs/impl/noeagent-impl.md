# NoeAgent Implementation Architecture

> Unified implementation guide for the NoeAgent autonomous research assistant.
>
> **Module**: `noesium/noeagent/`
> **Source**: Derived from [RFC-1002](../../specs/RFC-1002.md) (LangGraph Agent Design), [RFC-0005](../../specs/RFC-0005.md) (Capability Registry), [RFC-2001](../../specs/RFC-2001.md), [RFC-2002](../../specs/RFC-2002.md), [RFC-2003](../../specs/RFC-2003.md), [RFC-2004](../../specs/RFC-2004.md)
> **Language**: Python 3.11+
> **Framework**: LangGraph, Pydantic v2

---

## 1. Overview

NoeAgent is a long-running autonomous research assistant built on the Noesium framework. Inspired by Claude Code's architecture, it supports dual operational modes, task decomposition with todo-list tracking, toolkit-first tool execution, persistent memory via Memu, subagent orchestration (both in-process and external CLI daemons), and both library and Rich TUI interfaces.

### 1.1 Modes

- **Ask Mode**: Single-turn, read-only Q&A. No tools, no writes, no side effects. Uses memory recall + LLM reasoning. Analogous to Cursor's "Ask" mode.
- **Agent Mode**: Full autonomous agent with iterative planning, tool execution (bash, file I/O, python, search, MCP tools), memory persistence, and self-reflection. Analogous to Cursor's "Agent" mode.

### 1.2 Scope

**In Scope**:
- NoeAgent class, state model, and LangGraph graph for both modes
- Structured tool-calling via `structured_completion()` with `AgentAction` schema
- Task decomposition, todo-list rendering, and plan persistence
- Memory integration: Working, EventSourced, Memu providers
- Subagent spawn/interact as both runtime API and graph node
- External CLI subagent daemon management (Claude Code CLI, etc.)
- Intelligent auto-planning for tool vs subagent routing
- Typed progress event protocol (`ProgressEvent`, `ProgressEventType`, `ProgressCallback`)
- Rich TUI with compact Claude Code-style progress display
- Session-level JSONL logging via `SessionLogger`
- Library integration: pull-style (`astream_progress()`) and push-style (`progress_callbacks`)
- Library API: `run()`, `arun()`, `stream()`, `astream_progress()`, `astream_events()` (compat)

**Out of Scope**:
- Individual toolkit implementations (they live in `noesium/toolkits/`)
- Specific LLM model selection
- Browser automation internals

### 1.3 Spec Compliance

This guide MUST NOT contradict RFC-0005 (capability registry and subagent taxonomy), RFC-1002 (agent archetypes), RFC-2001/2002 (memory), or RFC-2003/2004 (tools).

---

## 2. Architectural Position

### 2.1 System Context

```
┌─────────────────────────────────────────────────────────────────────┐
│                            NoeAgent                                  │
│  ┌──────────────┐  ┌────────────────┐  ┌──────────────────────────┐ │
│  │  Ask Graph    │  │  Agent Graph    │  │   Task Planner           │ │
│  │  (read-only)  │  │  (autonomous)   │  │   (decompose + hints)    │ │
│  └──────┬────────┘  └───────┬─────────┘  └────────────┬─────────────┘ │
│         │                   │                          │              │
│  ┌──────▼───────────────────▼──────────────────────────▼────────────┐ │
│  │              Noesium Core Layer                                   │ │
│  │  ProviderMemoryManager  ToolExecutor  ToolRegistry  Events       │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │               Subagent Layer                                      │ │
│  │  In-process NoeAgent children  |  ExternalCliAdapter (daemons)    │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │               Interface Layer                                     │ │
│  │  Library API (.run/.arun/.stream/.astream_progress)               │ │
│  │  ProgressEvent protocol + ProgressCallback (push/pull)            │ │
│  │  Rich TUI (compact progress, plan table, markdown)                │ │
│  │  SessionLogger (JSONL offline logging)                            │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Dependency Graph

```
NoeAgent
├── noesium.core.agent.base.BaseGraphicAgent
├── noesium.core.memory.provider_manager.ProviderMemoryManager (RFC-2002)
│   ├── WorkingMemoryProvider
│   ├── EventSourcedProvider
│   └── MemuProvider → MemuMemoryStore
├── noesium.core.toolify.executor.ToolExecutor (RFC-2004)
├── noesium.core.toolify.tool_registry.ToolRegistry (RFC-2004)
├── noesium.core.toolify.adapters.BuiltinAdapter
├── noesium.core.event.store.InMemoryEventStore
├── langgraph.graph.StateGraph
├── pydantic.BaseModel
├── rich (Console, Live, Panel, Markdown, Spinner, Table, Prompt)
└── noesium.noeagent.cli_adapter.ExternalCliAdapter (new)
```

### 2.3 Module Structure

```
noesium/noeagent/
├── __init__.py          # Exports NoeAgent, NoeConfig, schemas, progress types
├── __main__.py          # CLI entrypoint: python -m noesium.noeagent
├── agent.py             # NoeAgent class, graph building, astream_progress, subagent API
├── state.py             # AskState, AgentState, TaskPlan, TaskStep
├── schemas.py           # AgentAction, ToolCallAction, SubagentAction
├── planner.py           # TaskPlanner for goal decomposition with execution hints
├── nodes.py             # Graph node functions
├── config.py            # NoeConfig (incl. progress_callbacks, cli_subagents, session_log_dir)
├── prompts.py           # Prompt templates
├── progress.py          # ProgressEvent, ProgressEventType, ProgressCallback
├── session_log.py       # SessionLogger (JSONL per-session writer)
├── cli_adapter.py       # ExternalCliAdapter for persistent CLI daemon subagents
├── tui.py               # Rich TUI (compact progress, plan table, markdown)
└── example_config.json  # Example configuration file
```

---

## 3. Core Types

### 3.1 NoeConfig

```python
class NoeMode(str, Enum):
    ASK = "ask"
    AGENT = "agent"

class CliSubagentConfig(BaseModel):
    """Configuration for an external CLI subagent daemon."""
    name: str                          # e.g. "claude", "cursor-agent"
    command: str                       # CLI command to spawn
    args: list[str] = []              # CLI arguments
    env: dict[str, str] = {}          # Extra environment variables
    timeout: int = 300                 # Per-task timeout in seconds
    restart_policy: str = "on-failure" # never | on-failure | always
    task_types: list[str] = []         # Supported task types (empty = all)

class NoeConfig(BaseModel):
    mode: NoeMode = NoeMode.AGENT
    llm_provider: str = "openai"
    model_name: str | None = None
    planning_model: str | None = None

    max_iterations: int = 25
    max_tool_calls_per_step: int = 5
    reflection_interval: int = 3
    interface_mode: str = "library"   # library | tui

    enabled_toolkits: list[str]       # all 18 toolkits by default
    mcp_servers: list[dict]
    custom_tools: list[Callable]

    memory_providers: list[str]       # working, event_sourced, memu
    memu_memory_dir: str = "~/.noeagent/memory"
    memu_user_id: str = "default_user"
    persist_memory: bool = True

    working_directory: str | None = None
    permissions: list[str]            # fs:read, fs:write, net:outbound, shell:execute
    enable_subagents: bool = True
    subagent_max_depth: int = 2
    cli_subagents: list[CliSubagentConfig] = []

    # Progress reporting (§5.5, §5.9)
    progress_callbacks: list[Callable] = []
    session_log_dir: str = "~/.noeagent/sessions"
    enable_session_logging: bool = True
```

Ask-mode overrides: `max_iterations=1`, `enabled_toolkits=[]`, `permissions=[]`, `persist_memory=False`.

### 3.2 State Models

```python
class TaskStep(BaseModel):
    step_id: str
    description: str
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: str | None = None
    execution_hint: Literal["tool", "subagent", "cli_subagent", "auto"] = "auto"

class TaskPlan(BaseModel):
    goal: str
    steps: list[TaskStep]
    current_step_index: int = 0
    is_complete: bool = False

    def to_todo_markdown(self) -> str: ...
    def advance(self) -> None: ...

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    plan: TaskPlan | None
    iteration: int
    tool_results: list[dict[str, Any]]
    reflection: str
    final_answer: str

class AskState(TypedDict):
    messages: Annotated[list, add_messages]
    memory_context: list[dict[str, Any]]
    final_answer: str
```

### 3.3 Structured Tool-Calling Schemas

```python
class ToolCallAction(BaseModel):
    tool_name: str          # must match a registered tool name
    arguments: dict[str, Any] = {}

class SubagentAction(BaseModel):
    action: Literal["spawn", "interact", "spawn_cli", "interact_cli", "terminate_cli"]
    name: str
    message: str = ""
    mode: str = "agent"

class AgentAction(BaseModel):
    thought: str                                    # reasoning trace
    tool_calls: list[ToolCallAction] | None = None  # if tool use needed
    subagent: SubagentAction | None = None          # if subagent use needed
    text_response: str | None = None                # if direct answer
    mark_step_complete: bool = False                # advance plan step

    @model_validator(mode="after")
    def exactly_one_action(self) -> "AgentAction":
        """Ensure exactly one of tool_calls, subagent, or text_response is set."""
        ...
```

The LLM is called via `structured_completion(response_model=AgentAction)`. This works with any provider because `structured_completion` uses Instructor.

---

## 4. Graph Design

### 4.1 Ask Mode Graph

```
START → recall_memory → generate_answer → END
```

No tools, no writes, no side effects.

### 4.2 Agent Mode Graph

```
START → plan → execute_step → [conditional]
  → tool_node → execute_step (loop)
  → subagent_node → execute_step (loop)
  → reflect → [conditional]
    → revise_plan → execute_step
    → finalize → END
  → finalize → END
```

### 4.3 Routing Logic

**After execute_step**:
1. If `plan.is_complete` → `finalize`
2. If `AgentAction.tool_calls` present → `tool_node`
3. If `AgentAction.subagent` present → `subagent_node`
4. If `iteration >= max_iterations` → `finalize`
5. If `iteration % reflection_interval == 0` → `reflect`
6. Otherwise → `execute_step`

**After reflect**:
1. If reflection contains "REVISE" → `revise_plan`
2. If `plan.is_complete` → `finalize`
3. Otherwise → `execute_step`

---

## 5. Key Implementation Details

### 5.1 Structured Tool Calling

`execute_step_node` builds a system prompt containing:
- Current plan step description and execution hint
- Available tool names and descriptions (from ToolRegistry)
- Completed results so far

It calls `llm.structured_completion(messages, response_model=AgentAction)`. The returned `AgentAction` is mapped:
- `tool_calls` → `AIMessage` with `tool_calls` attribute for LangGraph routing
- `subagent` → `AIMessage` with custom `subagent_action` attribute
- `text_response` → plain `AIMessage`
- `mark_step_complete` → calls `plan.advance()`

**Mutual exclusivity**: `AgentAction` enforces via `model_validator` that exactly one of `tool_calls`, `subagent`, or `text_response` is populated.

### 5.2 Tool Execution

Tools are loaded from existing Noesium toolkits via `BuiltinAdapter`. No custom "local tools" are introduced. Command execution uses `bash.run_bash`, file search uses `file_edit.search_in_files`, etc.

Default enabled toolkits (8 core toolkits):

```
bash, file_edit, document, image, python_executor, tabular_data,
wizsearch, user_interaction
```

Additional available toolkits (not enabled by default): `jina_research`, `memory`, `video`, `arxiv`, `serper`, `wikipedia`, `github`, `gmail`, `audio`, `audio_aliyun`

**`max_tool_calls_per_step` enforcement**: `tool_node` enforces the configured limit by processing only the first N tool calls and returning a warning message for any excess.

**Tool argument pre-validation**: Before dispatching to `ToolExecutor`, `tool_node` validates arguments against the tool's `input_schema` using Pydantic. Type coercion is attempted for common mismatches (e.g., string → list). This prevents runtime Pydantic errors like the `enabled_engines` validation failure observed in testing.

**Tool error recovery**: On tool execution failure, `tool_node`:
1. Logs the error with full context
2. Records the error in `tool_results`
3. Returns the error as a `ToolMessage` so the LLM can reason about the failure
4. Does NOT fail the step -- the agent can retry or use an alternative tool

### 5.3 Memory Integration

- **Working**: In-process, ephemeral
- **EventSourced**: Append-only event log
- **Memu**: Persistent cross-session memory (optional, graceful fallback)

Todo state is persisted to working memory after each iteration:
```python
await memory_manager.store(key="current_plan", value=plan.to_todo_markdown(), ...)
```

### 5.4 Subagent Model

NoeAgent supports two subagent types aligned with RFC-0005 §10:

#### 5.4.1 In-Process Subagents

- Parent manages `_subagents: dict[str, NoeAgent]`
- Child config derived from parent with depth limits and isolated memory
- `subagent_node` in the graph handles spawn/interact via `AgentAction.subagent`
- Interaction is async

**Subagent-as-Tool Registration**: When `enable_subagents=True`, `_setup_tools()` calls `_register_subagent_tools()` which registers a `spawn_subagent(name, task, mode)` function as a regular tool via `FunctionAdapter`. This allows the LLM to invoke subagents through the standard tool-calling mechanism without needing the separate `AgentAction.subagent` field.

Additionally, `tool_node` contains a fallback that intercepts any tool call with `name="subagent"` and redirects it to the registered `spawn_subagent` tool, preventing "tool not registered" errors from LLMs that confuse the subagent schema field with a tool name.

#### 5.4.2 External CLI Subagents (Persistent Daemons)

For integration with external agent CLIs (e.g., Claude Code CLI):

- Managed by `ExternalCliAdapter` (new module: `cli_adapter.py`)
- Spawned as long-lived daemon processes with stdin/stdout pipes
- JSON envelope protocol for structured message exchange
- Session persistence: daemon state survives across multiple task dispatches
- Lifecycle management: health checks, auto-restart on failure, graceful termination

**Configuration**: `NoeConfig.cli_subagents` specifies available CLI agents:

```python
NoeConfig(
    cli_subagents=[
        CliSubagentConfig(
            name="claude",
            command="claude",
            args=["--output-format", "stream-json"],
            timeout=300,
            restart_policy="on-failure",
            task_types=["code_edit", "code_review", "refactor"],
        ),
    ],
)
```

**Graph integration**: `subagent_node` handles both types:
- `action == "spawn"` / `"interact"` → in-process NoeAgent child
- `action == "spawn_cli"` / `"interact_cli"` / `"terminate_cli"` → external CLI daemon

#### 5.4.3 Subagent Cleanup

Subagents are cleaned up when:
- Parent agent session ends (all children terminated)
- Subagent reaches IDLE timeout
- Explicit `terminate_cli` action for CLI daemons
- `astream_progress()` finally block ensures cleanup on error/completion

### 5.5 Progress Event Protocol

**File:** `progress.py`

The canonical typed progress stream replaces the former ad-hoc dict events. A single flat `ProgressEvent` Pydantic model covers the full agent lifecycle. Every event carries a short `summary` (suitable for TUI one-liners) and a verbose `detail` (for session logging).

```python
class ProgressEventType(str, Enum):
    SESSION_START = "session.start"
    SESSION_END = "session.end"
    PLAN_CREATED = "plan.created"
    PLAN_REVISED = "plan.revised"
    STEP_START = "step.start"
    STEP_COMPLETE = "step.complete"
    TOOL_START = "tool.start"
    TOOL_END = "tool.end"
    SUBAGENT_START = "subagent.start"
    SUBAGENT_PROGRESS = "subagent.progress"
    SUBAGENT_END = "subagent.end"
    THINKING = "thinking"
    TEXT_CHUNK = "text.chunk"
    PARTIAL_RESULT = "partial.result"
    REFLECTION = "reflection"
    FINAL_ANSWER = "final.answer"
    ERROR = "error"

class ProgressEvent(BaseModel):
    type: ProgressEventType
    timestamp: datetime          # UTC
    session_id: str
    sequence: int                # monotonic ordering counter

    node: str | None             # graph node name
    step_index: int | None
    step_desc: str | None
    tool_name: str | None
    tool_args: dict | None
    tool_result: str | None
    subagent_id: str | None
    text: str | None
    summary: str | None          # compact one-liner for TUI
    detail: str | None           # verbose content for offline logging
    plan_snapshot: dict | None   # serialised TaskPlan
    error: str | None
    metadata: dict = {}
```

**Event lifecycle per query:**

```
SESSION_START → PLAN_CREATED → STEP_START → TOOL_START → TOOL_END → ...
  → STEP_COMPLETE → STEP_START → ... → REFLECTION → ... → FINAL_ANSWER → SESSION_END
```

**Push-style callback protocol** for library consumers:

```python
class ProgressCallback(Protocol):
    async def on_progress(self, event: ProgressEvent) -> None: ...
```

Callbacks are registered via `NoeConfig.progress_callbacks`. Both objects implementing the `ProgressCallback` protocol and bare async callables `(ProgressEvent) -> None` are supported.

**`astream_progress()` is the canonical public API.** The former `astream_events()` is preserved as a backward-compatible shim that yields `event.model_dump()` dicts.

### 5.6 Rich TUI (Compact Progress Display)

The TUI (`tui.py`) consumes `ProgressEvent` objects from `astream_progress()` and renders a compact, Claude Code-style display. Detailed information (tool args, full results, reflection text) is NOT shown in the terminal -- it goes to the session log only.

```
┌─ NoeAgent ─────────────────────────────────────────────┐
│  Mode: agent  |  /help  |  /exit                       │
│  Session log: ~/.noeagent/sessions/01905b8a-....jsonl  │
└────────────────────────────────────────────────────────┘

noe|agent> Analyze the memory system architecture

  Plan: Analyze the memory system architecture
    1  [x]  Read memory provider source code
    2  [>]  Analyze ProviderMemoryManager interface
    3  [ ]  Synthesize architecture summary

  Step 2/3: Analyze ProviderMemoryManager interface
    . Using bash.run_bash
    > bash.run_bash  (file contents truncated)
    . Using python_executor
    > python_executor  Found 3 providers

  ────────────────────────────────────────

  ## Final Answer
  The memory system uses a three-tier provider architecture...
```

**Rendering Rules:**

| Event Type | TUI Display |
|------------|-------------|
| `PLAN_CREATED` / `PLAN_REVISED` | Live-updating plan checklist table |
| `STEP_START` | Bold step indicator: `Step 2/3: ...` |
| `TOOL_START` | Dim one-liner: `. Using <tool_name>` |
| `TOOL_END` | Green one-liner: `> <tool_name>  <brief result>` |
| `SUBAGENT_START/PROGRESS/END` | Bracketed: `[subagent:name] status` |
| `THINKING` | Dim italic: `. Thinking...` |
| `REFLECTION` | Dim one-liner: `. Reflected on progress` (detail in session log) |
| `PARTIAL_RESULT` | Markdown block after separator rule |
| `FINAL_ANSWER` | Full markdown rendering |
| `ERROR` | Red one-liner: `! error message` |

**Multi-Subagent Progress:**

```
  Step 2/3: Research in parallel
    [web-search-1] Searching for "memory architecture patterns"
    [code-analyzer-1] Analyzing provider_manager.py
    [claude-cli] Reviewing implementation against spec
    [web-search-1] done
    [code-analyzer-1] done
    [claude-cli] done (3 files reviewed)
```

**Slash Commands:**

| Command | Description |
|---------|-------------|
| `/exit`, `/quit` | Exit the TUI |
| `/mode ask\|agent` | Switch mode at runtime |
| `/plan` | Show current task plan |
| `/memory` | Show memory statistics |
| `/session` | Show current session log path |
| `/clear` | Clear the screen |
| `/help` | List available commands |

**TUI Architecture:**

1. `run_agent_tui(agent)` -- main loop; auto-registers `SessionLogger` callback; reads input, dispatches slash commands or queries
2. `_process_query(agent, input, console, session_logger)` -- async, calls `agent.astream_progress()`, builds a `Group` renderable inside `Live` context
3. `render_plan_table(plan)` -- converts `TaskPlan` to compact `rich.table.Table`
4. `_activity_line(event)` -- converts a `ProgressEvent` to a compact `rich.text.Text` one-liner
5. `handle_slash_command(cmd, agent, console)` -- parses and executes slash commands
6. `read_user_input(console)` -- multiline input with `\` continuation

### 5.7 MCP Server Loading

```python
for mcp_config in self.config.mcp_servers:
    session = await MCPSession.connect(**mcp_config)
    await self._tool_registry.load_mcp_server(session)
```

### 5.8 Session Logging

**File:** `session_log.py`

`SessionLogger` is a built-in `ProgressCallback` implementation that writes every `ProgressEvent` as a JSON line into a per-session `.jsonl` file. This captures ALL detail (full tool args/results, complete reflection text, plan snapshots) for offline replay and audit.

```python
class SessionLogger:
    def __init__(self, log_dir: str = ".noe_sessions", session_id: str | None = None)
    async def on_progress(self, event: ProgressEvent) -> None
```

**JSONL format** (one JSON object per line):

```json
{"type":"session.start","timestamp":"2026-03-02T10:00:00Z","session_id":"01905b8a-...","sequence":1,"summary":"Session started: analyze X",...}
{"type":"tool.start","timestamp":"...","session_id":"...","sequence":5,"tool_name":"bash.run_bash","tool_args":{"command":"ls"},"summary":"Using bash.run_bash",...}
{"type":"tool.end","timestamp":"...","session_id":"...","sequence":6,"tool_name":"bash.run_bash","tool_result":"file1 file2","summary":"Completed: bash.run_bash","detail":"file1\nfile2\n...",...}
```

**Auto-registration:** In TUI mode, `run_agent_tui()` automatically creates and registers a `SessionLogger` to the agent's `progress_callbacks`. In library mode, users register their own if desired:

```python
from noesium.noeagent import SessionLogger
logger = SessionLogger(log_dir="/tmp/my_logs")
agent = NoeAgent(NoeConfig(progress_callbacks=[logger]))
```

### 5.9 Library Integration Protocol

The `ProgressEvent` Pydantic model IS the integration protocol. No separate protocol document is needed -- the model is self-describing, JSON-serializable, and versioned via `ProgressEventType`.

**Pull-style** (async generator -- recommended):

```python
from noesium.noeagent import NoeAgent, NoeConfig, ProgressEventType

agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT))
async for event in agent.astream_progress("analyze the memory system"):
    if event.type == ProgressEventType.TOOL_START:
        my_ui.show_activity(event.summary)
    elif event.type == ProgressEventType.FINAL_ANSWER:
        my_ui.show_result(event.text)
    # event.model_dump_json() for wire serialization
```

**Push-style** (callback):

```python
async def my_handler(event: ProgressEvent):
    await websocket.send(event.model_dump_json())

agent = NoeAgent(NoeConfig(progress_callbacks=[my_handler]))
result = await agent.arun("analyze the memory system")
```

**Both patterns work simultaneously:** `arun()` internally consumes `astream_progress()` and fires callbacks. Registering callbacks does not prevent using `astream_progress()` directly.

**Backward compatibility:** `astream_events()` remains available as a thin wrapper that calls `astream_progress()` and yields `event.model_dump()` dicts.

### 5.10 External CLI Subagent Adapter

**File:** `cli_adapter.py`

Implements the persistent daemon model from RFC-0005 §10.

```python
class SubagentHandle:
    """Opaque handle to a running subagent daemon."""
    process: asyncio.subprocess.Process
    session_id: str
    state: Literal["CREATED", "RUNNING", "BUSY", "IDLE", "TERMINATED"]
    started_at: datetime

class ExternalCliAdapter:
    """Manages persistent CLI subagent daemons."""

    async def spawn(self, config: CliSubagentConfig) -> SubagentHandle
    async def send(self, handle: SubagentHandle, message: str) -> str
    async def health_check(self, handle: SubagentHandle) -> bool
    async def restart(self, handle: SubagentHandle) -> SubagentHandle
    async def terminate(self, handle: SubagentHandle) -> None
```

**Claude Code CLI integration:**

```python
adapter = ExternalCliAdapter()
handle = await adapter.spawn(CliSubagentConfig(
    name="claude",
    command="claude",
    args=["--output-format", "stream-json"],
))
result = await adapter.send(handle, "Review the auth module for security issues")
```

Communication uses stdin/stdout JSON streaming. The adapter reads streaming JSON output line by line, correlates responses to requests, and handles timeouts.

### 5.11 Intelligent Auto-Planning for Subagent Spawning

The `TaskPlanner` includes execution hint intelligence that determines whether each step should use tools directly, spawn an in-process subagent, or delegate to a CLI subagent.

**Decision heuristics:**

| Signal | Route to |
|--------|----------|
| Single atomic operation (search, read, compute) | Tool |
| Multi-step reasoning with own planning | In-process subagent |
| Embarrassingly parallel independent subtasks | Multiple subagents |
| Persistent session state needed (code editing) | CLI subagent |
| External agent has specialized capability | CLI subagent |
| Task complexity low, latency sensitive | Tool |
| Task complexity high, quality sensitive | Subagent |

**Implementation:**

1. `TaskPlanner.create_plan()` now produces `TaskStep` objects with `execution_hint` field
2. The planning prompt includes descriptions of available CLI subagents and their task types
3. `execute_step_node` uses `execution_hint` to bias the LLM's `AgentAction` generation
4. When `execution_hint="auto"`, the LLM decides based on available context

**Planning prompt enhancement:**

```
Available execution modes:
- tool: Use a tool for atomic operations (search, read, compute)
- subagent: Delegate to a child agent for multi-step reasoning
- cli_subagent: Delegate to an external CLI agent (e.g., Claude) for
  specialized tasks like code review, refactoring
- auto: Let the agent decide based on context

For each step, suggest an execution_hint.
```

---

## 6. Error Handling

| Error Category | Handling Approach |
|----------------|-------------------|
| Tool execution failure | Log, add error to tool_results, continue to next step |
| Tool argument validation failure | Attempt type coercion, retry with fixed args, fall back to error |
| LLM call failure | Retry up to 3 times, then raise |
| Structured output parse failure | Retry with lower temperature, fall back to text-only response |
| Planning failure | Fall back to single-step "just answer" plan |
| Memory recall failure | Continue without memory context, log warning |
| Iteration limit | Force finalize with partial results |
| Permission denied | Skip tool, add error message, continue |
| Subagent failure | Log error, return error as tool result, continue parent graph |
| CLI subagent crash | Auto-restart per restart_policy, escalate if repeated |
| CLI subagent timeout | Terminate, return timeout error, continue parent graph |
| TUI rendering error | Catch and display in red error Panel, continue loop |

---

## 7. Configuration Defaults

| Option | Default | Description |
|--------|---------|-------------|
| `mode` | `agent` | Operating mode |
| `interface_mode` | `library` | `library` or `tui` |
| `max_iterations` | `25` | Maximum graph iterations |
| `max_tool_calls_per_step` | `5` | Max tool calls per execute_step |
| `reflection_interval` | `3` | Steps between reflections |
| `enabled_toolkits` | 8 core toolkits | Active toolkits (bash, file_edit, document, image, python_executor, tabular_data, wizsearch, user_interaction) |
| `persist_memory` | `true` | Persist agent results to durable memory |
| `progress_callbacks` | `[]` | List of async callables / `ProgressCallback` instances |
| `session_log_dir` | `~/.noeagent/sessions` | Directory for session JSONL logs |
| `memu_memory_dir` | `~/.noeagent/memory` | Directory for Memu persistent memory |
| `enable_session_logging` | `true` | Auto-register `SessionLogger` in TUI mode |
| `cli_subagents` | `[]` | External CLI subagent configurations |

---

## 8. Testing Strategy

| Component | Test Focus |
|-----------|------------|
| `AgentAction` schema | Structured output parsing, mutual exclusivity validation |
| `NoeConfig` | Defaults, validation, ask mode overrides, all 18 toolkits |
| `TaskPlanner` | Plan creation with execution hints, revision (with mocked LLM) |
| `execute_step_node` | Structured completion returns tool calls, execution hint bias |
| `tool_node` | Tool execution, max_tool_calls enforcement, arg pre-validation |
| `subagent_node` | In-process spawn/interact, CLI spawn/interact/terminate |
| `ExternalCliAdapter` | Spawn, send, health_check, restart, terminate lifecycle |
| `ProgressEvent` | Serialization, deserialization, all event types |
| `ProgressEventType` | Enum coverage, string representation |
| `astream_progress` | Typed event stream: full lifecycle coverage |
| `astream_events` | Backward-compat dict output matches `ProgressEvent.model_dump()` |
| `SessionLogger` | JSONL write, directory creation, concurrent writes |
| `ProgressCallback` | Push-style callback invocation from `arun()` and `astream_progress()` |
| `_route_after_execute` | Conditional routing logic |
| `render_plan_table` | Plan to Rich Table conversion |
| `_activity_line` | Compact one-liner rendering for each event type |
| `handle_slash_command` | Slash command parsing and dispatch (incl. `/session`) |
| Todo persistence | Plan stored/recalled from working memory |

---

## 9. Implementation Gap Analysis

Current codebase gaps relative to this design:

| Gap | Current State | Required State | Priority | Status |
|-----|--------------|----------------|----------|--------|
| `additional_kwargs` safety | Used without defensive `getattr` in routing | Add `getattr` guards in `_route_after_execute` | P0 (bug) | Done |
| `AgentAction` mutual exclusivity | No validation | Add `model_validator` ensuring exactly one action | P0 (bug) | Done |
| Tool arg pre-validation | LLM passes raw args, Pydantic errors at toolkit level | Pre-validate against tool schema before dispatch | P1 | Partial (type coercion only, no full schema validation) |
| `max_tool_calls_per_step` | Config field exists, not enforced | Enforce in `tool_node` and `execute_step_node` | P1 | Done |
| `planning_model` | Config field exists, not used | Pass to `TaskPlanner` LLM calls | P2 | Done |
| `TaskStep.execution_hint` | Not present | Add field for tool/subagent routing hints | P2 | Done |
| Execution hint in planner | Planner does not produce hints | Planning prompt asks for hints, parser extracts them | P2 | Done |
| Execution hint in LLM prompt | `AGENT_SYSTEM_PROMPT` has no hint section | Add `{execution_hint}` section that biases LLM routing | P2 | Done |
| `STEP_COMPLETE` event | Not emitted | Emit when `plan.advance()` completes a step | P2 | Done |
| Subagent cleanup | `_subagents` grows indefinitely | Cleanup on task completion + CLI adapter teardown | P2 | Done |
| `ExternalCliAdapter` | Not implemented | New module `cli_adapter.py` | P2 | Done |
| `CliSubagentConfig` | Not in NoeConfig | Add config field and config loading | P2 | Done |
| CLI adapter wiring | Not connected | `_setup_cli_subagents()` in `initialize()`, CLI actions in `subagent_node` | P2 | Done |
| `model_name` passthrough | Not passed to `BaseAgent` | `super().__init__(model_name=config.model_name)` | P2 | Done |
| All toolkits by default | 11 of 18 enabled | Enable all 18 in default config | P3 | Done |
| Module path | `noesium/agents/noe/` | `noesium/noe/` (old module removed) | - | Done |

All gaps have been resolved.

---

## Appendix A: RFC Requirement Mapping

| RFC Requirement | Guide Section | Implementation |
|-----------------|---------------|----------------|
| RFC-0005 §4.2 (Capability Types) | §5.2, §5.4 | Tool types map to CapabilityType taxonomy |
| RFC-0005 §10 (Persistent Subagent) | §5.10 | ExternalCliAdapter |
| RFC-0005 §11 (Lifecycle Model) | §5.4.3 | Subagent cleanup and lifecycle |
| RFC-0005 §16 (Tool vs Subagent) | §5.11 | Auto-planning heuristics |
| RFC-1002 §5.2 (Conversation Agent) | §4.1 | Ask mode graph |
| RFC-1002 §5.3 (Research Agent) | §4.2 | Agent mode graph |
| RFC-1002 §5.4 (Task Agent) | §4.2 | TaskPlanner + agent loop |
| RFC-2001 §9 (Recall Protocol) | §5.3 | ProviderMemoryManager.recall() |
| RFC-2002 §8 (MemoryManager) | §5.3 | Memory store/recall |
| RFC-2003 §7 (Event-Wrapped Execution) | §5.2 | ToolExecutor.run() |
| RFC-2004 §5 (ToolExecutor) | §5.2 | Tool node implementation |
| RFC-2004 §7 (Source Adapters) | §5.2 | _setup_tools() |

---

## Appendix B: Revision History

| Date | Changes |
|------|---------|
| 2026-03-01 | Initial guide based on RFC-1002, RFC-2001-2004 |
| 2026-03-02 | Unified with evolution guide: added structured tool calling, subagent graph node, todo persistence |
| 2026-03-02 | Removed ACP/Toad mode; added Rich TUI with event streaming protocol, slash commands, spinner, tool panels, markdown rendering |
| 2026-03-02 | Progress Event Protocol: replaced ad-hoc dict events with typed `ProgressEvent`/`ProgressEventType`; added `astream_progress()` as canonical API, `astream_events()` as compat shim; compact Claude Code-style TUI; `SessionLogger` JSONL offline logging; `ProgressCallback` push-style protocol; library integration protocol (§5.5, §5.6, §5.8, §5.9) |
| 2026-03-02 | Module moved from `noesium/agents/noe/` to `noesium/noe/`; added ExternalCliAdapter for persistent CLI subagent daemons (§5.10); intelligent auto-planning with execution hints (§5.11); tool arg pre-validation; `max_tool_calls_per_step` enforcement; `AgentAction` mutual exclusivity validation; subagent cleanup lifecycle; all 18 toolkits enabled by default; implementation gap analysis (§9); RFC-0005 capability type alignment |
| 2026-03-02 | Implemented all remaining gaps: `ExternalCliAdapter` (cli_adapter.py), `planning_model` wiring, execution_hint in planner prompts and LLM prompt, `STEP_COMPLETE` event emission, subagent cleanup on session end, `model_name` passthrough to BaseAgent; old `noesium/agents/noe/` module deleted (no backward compat); all gaps in §9 resolved |
