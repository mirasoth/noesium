# NoeAgent Implementation Architecture

> Unified implementation guide for the NoeAgent autonomous research assistant.
>
> **Module**: `noesium/agents/noe/`
> **Source**: Derived from [RFC-1002](../../specs/RFC-1002.md) (LangGraph Agent Design), [RFC-2001](../../specs/RFC-2001.md), [RFC-2002](../../specs/RFC-2002.md), [RFC-2003](../../specs/RFC-2003.md), [RFC-2004](../../specs/RFC-2004.md)
> **Language**: Python 3.11+
> **Framework**: LangGraph, Pydantic v2

---

## 1. Overview

NoeAgent is a long-running autonomous research assistant built on the Noesium framework. Inspired by Claude Code's architecture, it supports dual operational modes, task decomposition with todo-list tracking, toolkit-first tool execution, persistent memory via Memu, subagent orchestration, and both library and Rich TUI interfaces.

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
- Rich TUI with streaming events, spinner, tool panels, markdown rendering
- Library API: `run()`, `arun()`, `stream()`, `astream_events()`

**Out of Scope**:
- Individual toolkit implementations (they live in `noesium/toolkits/`)
- Specific LLM model selection
- Browser automation internals

### 1.3 Spec Compliance

This guide MUST NOT contradict RFC-1002 (agent archetypes), RFC-2001/2002 (memory), or RFC-2003/2004 (tools).

---

## 2. Architectural Position

### 2.1 System Context

```
┌────────────────────────────────────────────────────────────────┐
│                         NoeAgent                               │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────────┐  │
│  │  Ask Graph    │  │  Agent Graph    │  │   Task Planner     │  │
│  │  (read-only)  │  │  (autonomous)   │  │   (decompose)      │  │
│  └──────┬────────┘  └───────┬─────────┘  └──────────┬─────────┘  │
│         │                   │                        │           │
│  ┌──────▼───────────────────▼────────────────────────▼─────────┐ │
│  │              Noesium Core Layer                              │ │
│  │  ProviderMemoryManager  ToolExecutor  ToolRegistry  Events  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │               Interface Layer                               │ │
│  │  Library API (.run/.arun/.stream/.astream_events)           │ │
│  │  Rich TUI (spinner, panels, markdown, plan table)           │ │
│  └─────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
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
└── rich (Console, Live, Panel, Markdown, Spinner, Table, Prompt)
```

### 2.3 Module Structure

```
noesium/agents/noe/
├── __init__.py          # Exports NoeAgent, NoeConfig, schemas
├── agent.py             # NoeAgent class, graph building, astream_events, subagent API
├── state.py             # AskState, AgentState, TaskPlan, TaskStep
├── schemas.py           # AgentAction, ToolCallAction (structured output)
├── planner.py           # TaskPlanner for goal decomposition
├── nodes.py             # Graph node functions
├── config.py            # NoeConfig
├── prompts.py           # Prompt templates
└── tui.py               # Rich TUI (spinner, panels, markdown, slash commands)
```

---

## 3. Core Types

### 3.1 NoeConfig

```python
class NoeMode(str, Enum):
    ASK = "ask"
    AGENT = "agent"

class NoeConfig(BaseModel):
    mode: NoeMode = NoeMode.AGENT
    llm_provider: str = "openrouter"
    model_name: str | None = None
    planning_model: str | None = None

    max_iterations: int = 25
    max_tool_calls_per_step: int = 5
    reflection_interval: int = 3
    interface_mode: str = "library"   # library | tui

    enabled_toolkits: list[str]       # bash, python_executor, file_edit, ...
    mcp_servers: list[dict]
    custom_tools: list[Callable]

    memory_providers: list[str]       # working, event_sourced, memu
    memu_memory_dir: str = ".noe_memory"
    memu_user_id: str = "default_user"
    persist_memory: bool = True

    working_directory: str | None = None
    permissions: list[str]            # fs:read, fs:write, net:outbound, shell:execute
    enable_subagents: bool = True
    subagent_max_depth: int = 2
```

Ask-mode overrides: `max_iterations=1`, `enabled_toolkits=[]`, `permissions=[]`, `persist_memory=False`.

### 3.2 State Models

```python
class TaskStep(BaseModel):
    step_id: str
    description: str
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: str | None = None

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
    action: Literal["spawn", "interact"]
    name: str
    message: str = ""
    mode: str = "agent"

class AgentAction(BaseModel):
    thought: str                                    # reasoning trace
    tool_calls: list[ToolCallAction] | None = None  # if tool use needed
    subagent: SubagentAction | None = None          # if subagent use needed
    text_response: str | None = None                # if direct answer
    mark_step_complete: bool = False                # advance plan step
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
- Current plan step description
- Available tool names and descriptions (from ToolRegistry)
- Completed results so far

It calls `llm.structured_completion(messages, response_model=AgentAction)`. The returned `AgentAction` is mapped:
- `tool_calls` → `AIMessage` with `tool_calls` attribute for LangGraph routing
- `subagent` → `AIMessage` with custom `subagent_action` attribute
- `text_response` → plain `AIMessage`
- `mark_step_complete` → calls `plan.advance()`

### 5.2 Tool Execution

Tools are loaded from existing Noesium toolkits via `BuiltinAdapter`. No custom "local tools" are introduced. Command execution uses `bash.run_bash`, file search uses `file_edit.search_in_files`, etc.

Default enabled toolkits: `bash`, `python_executor`, `file_edit`, `search`, `memory`, `document`, `image`, `tabular_data`, `video`, `user_interaction`.

### 5.3 Memory Integration

- **Working**: In-process, ephemeral
- **EventSourced**: Append-only event log
- **Memu**: Persistent cross-session memory (optional, graceful fallback)

Todo state is persisted to working memory after each iteration:
```python
await memory_manager.store(key="current_plan", value=plan.to_todo_markdown(), ...)
```

### 5.4 Subagent Model

- Parent manages `_subagents: dict[str, NoeAgent]`
- Child config derived from parent with depth limits and isolated memory
- `subagent_node` in the graph handles spawn/interact via `AgentAction.subagent`
- Interaction is async

### 5.5 Event Streaming Protocol

The `astream_events()` async generator bridges LangGraph node outputs and the TUI. It iterates over `compiled.astream(initial)` and translates node outputs into typed event dicts:

| Event Type | Fields | Emitted By |
|------------|--------|------------|
| `plan_created` | `plan: TaskPlan` | `plan_node`, `revise_plan_node` |
| `step_started` | `step: str`, `index: int` | when plan step advances |
| `tool_call_started` | `name: str`, `args: dict` | `execute_step_node` (from `AIMessage.tool_calls`) |
| `tool_call_completed` | `name: str`, `result: str` | `tool_node` (from `tool_results`) |
| `thinking` | `thought: str` | subagent delegation |
| `text_chunk` | `text: str` | intermediate text from LLM |
| `reflection` | `text: str` | `reflect_node` |
| `final_answer` | `text: str` | `finalize_node` |

```python
async def astream_events(self, user_message: str) -> AsyncGenerator[dict, None]:
    # ... initialize graph ...
    async for event in compiled.astream(initial):
        for node_name, node_output in event.items():
            # inspect plan, tool_results, messages, reflection, final_answer
            # yield typed event dicts
```

### 5.6 Rich TUI

The TUI (`tui.py`) consumes events from `astream_events()` and renders them using Rich components:

```
┌───────────────────────────────────────────────────┐
│  NoeAgent — Autonomous Research Assistant          │
│  Mode: agent  |  /help for commands, /exit to quit │
└───────────────────────────────────────────────────┘

noe> How does the memory system work?

⠋ Thinking...

┌── Plan: Analyze memory system ────────────────────┐
│ #  │ Status │ Step                                 │
│ 1  │ [x]    │ Read memory provider code            │
│ 2  │ [>]    │ Analyze provider manager              │
│ 3  │ [ ]    │ Summarize architecture                │
└───────────────────────────────────────────────────┘

┌── Tool: bash.run_bash ───────────────────────────┐
│ {"command": "cat noesium/core/memory/..."}       │
│ --- result ---                                    │
│ (file contents)                                   │
└──────────────────────────────────────────────────┘

## Memory System Architecture
The memory system uses a provider-based approach...
```

**Rich Components Used:**

| Component | Purpose |
|-----------|---------|
| `Console` | Primary output handle |
| `Live` | Live-updating display for spinner during processing |
| `Spinner` | Shows "Thinking...", "Executing tool: X", step status |
| `Panel` | Wraps tool calls, errors, reflections |
| `Markdown` | Renders final answers and text chunks |
| `Table` | Todo/plan checklist rendering |
| `Prompt` | Styled `noe>` input with multiline (backslash continuation) |
| `Text` | Styled status markers and fragments |

**Slash Commands:**

| Command | Description |
|---------|-------------|
| `/exit`, `/quit` | Exit the TUI |
| `/mode ask\|agent` | Switch mode at runtime |
| `/plan` | Show current task plan |
| `/memory` | Show memory statistics |
| `/clear` | Clear the screen |
| `/help` | List available commands |

**TUI Architecture:**

1. `run_agent_tui(agent)` — main loop, reads input, dispatches slash commands or queries
2. `_process_query(agent, input, console)` — async, calls `agent.astream_events()`, renders events with `Live` context
3. `render_plan_table(plan)` — converts `TaskPlan` to `rich.table.Table`
4. `render_tool_call_panel(name, args, result)` — creates `rich.panel.Panel` for tool calls
5. `handle_slash_command(cmd, agent, console)` — parses and executes slash commands
6. `read_user_input(console)` — multiline input with `\` continuation

### 5.7 MCP Server Loading

```python
for mcp_config in self.config.mcp_servers:
    session = await MCPSession.connect(**mcp_config)
    await self._tool_registry.load_mcp_server(session)
```

---

## 6. Error Handling

| Error Category | Handling Approach |
|----------------|-------------------|
| Tool execution failure | Log, add error to tool_results, continue to next step |
| LLM call failure | Retry up to 3 times, then raise |
| Structured output parse failure | Retry with lower temperature, fall back to text-only response |
| Planning failure | Fall back to single-step "just answer" plan |
| Memory recall failure | Continue without memory context, log warning |
| Iteration limit | Force finalize with partial results |
| Permission denied | Skip tool, add error message, continue |
| Subagent failure | Log error, return error as tool result, continue parent graph |
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
| `enabled_toolkits` | `[bash, python_executor, file_edit, search, memory, document, image, tabular_data, video, user_interaction]` | Active toolkits |
| `persist_memory` | `true` | Persist agent results to durable memory |

---

## 8. Testing Strategy

| Component | Test Focus |
|-----------|------------|
| `AgentAction` schema | Structured output parsing, tool_call and subagent fields |
| `NoeConfig` | Defaults, validation, ask mode overrides |
| `TaskPlanner` | Plan creation, revision (with mocked LLM) |
| `execute_step_node` | Structured completion returns tool calls |
| `tool_node` | Tool execution with mocked ToolExecutor |
| `subagent_node` | Spawn and interaction |
| `astream_events` | Event types emitted for plan, tool, text, final answer |
| `_route_after_execute` | Conditional routing logic |
| `render_plan_table` | Plan → Rich Table conversion |
| `handle_slash_command` | Slash command parsing and dispatch |
| Todo persistence | Plan stored/recalled from working memory |

---

## Appendix A: RFC Requirement Mapping

| RFC Requirement | Guide Section | Implementation |
|-----------------|---------------|----------------|
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
