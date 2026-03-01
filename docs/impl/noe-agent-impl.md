# NoeAgent Implementation Architecture

> Implementation guide for the NoeAgent research assistant in Noesium.
>
> **Module**: `noesium/agents/noe/`
> **Source**: Derived from [RFC-1002](../../specs/RFC-1002.md) (LangGraph Agent Design), [RFC-2001](../../specs/RFC-2001.md), [RFC-2002](../../specs/RFC-2002.md), [RFC-2003](../../specs/RFC-2003.md), [RFC-2004](../../specs/RFC-2004.md)
> **Related RFCs**: [RFC-0001](../../specs/RFC-0001.md), [RFC-0002](../../specs/RFC-0002.md), [RFC-0003](../../specs/RFC-0003.md), [RFC-0004](../../specs/RFC-0004.md), [RFC-0005](../../specs/RFC-0005.md), [RFC-1001](../../specs/RFC-1001.md)
> **Language**: Python 3.11+
> **Framework**: LangGraph, Pydantic v2

---

## 1. Overview

NoeAgent is a long-running autonomous research assistant built on the Noesium framework. It operates in two modes:

- **Ask Mode**: Single-turn, read-only question answering. No tool execution, no file writes, no side effects. Uses memory recall and LLM reasoning to answer queries. Analogous to Cursor's "Ask" mode.

- **Agent Mode**: Full autonomous agent with iterative planning, tool execution (web search, code execution, file I/O, bash, MCP tools), memory persistence, and self-reflection. Analogous to Cursor's "Agent" mode.

### 1.1 Purpose

This document specifies the implementation architecture for NoeAgent. It provides:

- Module structure and file layout
- State model and LangGraph graph design
- Mode-specific execution paths
- Tool integration via ToolExecutor (RFC-2004)
- Memory integration via MemoryManager (RFC-2002)
- Task planning and iterative refinement
- Error handling and configuration

### 1.2 Scope

**In Scope**:
- NoeAgent class hierarchy and state model
- LangGraph graph for both ask and agent modes
- Tool binding and execution flow
- Memory read/write integration
- Configuration and mode switching
- Unit and integration test strategy

**Out of Scope**:
- UI/CLI implementation
- Specific LLM model selection
- Browser automation internals
- Individual tool implementations

### 1.3 Spec Compliance

This guide MUST NOT contradict RFC-1002 (agent archetypes), RFC-2001/2002 (memory), or RFC-2003/2004 (tools). All invariants from source RFCs are preserved.

---

## 2. Architectural Position

### 2.1 System Context

```
┌───────────────────────────────────────────────────────────────┐
│                     NoeAgent                               │
│  ┌─────────────┐  ┌───────────────┐  ┌─────────────────────┐ │
│  │  Ask Graph   │  │  Agent Graph   │  │   Task Planner      │ │
│  │  (read-only) │  │  (autonomous)  │  │   (goal decompose)  │ │
│  └──────┬───────┘  └───────┬────────┘  └──────────┬──────────┘ │
│         │                  │                       │            │
│  ┌──────▼──────────────────▼───────────────────────▼──────────┐ │
│  │              Noesium Core Layer                              │ │
│  │  MemoryManager  ToolExecutor  KernelExecutor  EventStore   │ │
│  └─────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

### 2.2 Dependency Graph

```
NoeAgent
├── noesium.core.agent.base.BaseGraphicAgent
├── noesium.core.memory.manager.MemoryManager (RFC-2002)
├── noesium.core.toolify.executor.ToolExecutor (RFC-2004)
├── noesium.core.toolify.tool_registry.ToolRegistry (RFC-2004)
├── noesium.core.event.store.EventStore (RFC-1001)
├── noesium.core.kernel.executor.KernelExecutor (RFC-1001)
├── noesium.core.projection.engine.ProjectionEngine (RFC-1001)
├── langgraph.graph.StateGraph
└── pydantic.BaseModel
```

### 2.3 Module Responsibilities

| Module | Responsibility | Dependencies |
|--------|----------------|--------------|
| `agent.py` | Main NoeAgent class, graph building, mode dispatch | All below |
| `state.py` | Pydantic state models for ask and agent graphs | pydantic |
| `planner.py` | Task decomposition and planning | LLM client |
| `nodes.py` | Graph node implementations | state, tools, memory |
| `config.py` | AlithiaConfig with mode, tools, memory settings | pydantic |
| `prompts.py` | System prompts for ask and agent modes | --- |

---

## 3. Module Structure

```
noesium/agents/noe/
├── __init__.py          # Exports NoeAgent, AlithiaConfig
├── agent.py             # NoeAgent class
├── state.py             # AlithiaState, AskState, AgentState, TaskPlan
├── planner.py           # TaskPlanner for goal decomposition
├── nodes.py             # Graph node functions
├── config.py            # AlithiaConfig
└── prompts.py           # Prompt templates
```

---

## 4. Core Types

### 4.1 AlithiaConfig

```python
class AlithiaMode(str, Enum):
    ASK = "ask"
    AGENT = "agent"

class AlithiaConfig(BaseModel):
    mode: AlithiaMode = AlithiaMode.AGENT
    llm_provider: str = "openrouter"
    model_name: str | None = None
    planning_model: str | None = None

    max_iterations: int = 25
    max_tool_calls_per_step: int = 5
    reflection_interval: int = 3

    enabled_toolkits: list[str] = Field(default_factory=lambda: [
        "search", "bash", "python_executor", "file_edit",
    ])
    mcp_servers: list[dict[str, Any]] = Field(default_factory=list)
    custom_tools: list[Callable] = Field(default_factory=list)

    memory_providers: list[str] = Field(default_factory=lambda: ["working", "event_sourced"])
    persist_memory: bool = True

    working_directory: str | None = None
    permissions: list[str] = Field(default_factory=lambda: [
        "fs:read", "fs:write", "net:outbound", "shell:execute",
    ])

    model_config = ConfigDict(arbitrary_types_allowed=True)
```

### 4.2 AlithiaState (Agent Mode)

```python
class TaskStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid7str()))
    description: str
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: str | None = None

class TaskPlan(BaseModel):
    goal: str
    steps: list[TaskStep] = Field(default_factory=list)
    current_step_index: int = 0
    is_complete: bool = False

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    plan: TaskPlan | None
    iteration: int
    tool_results: list[dict[str, Any]]
    reflection: str
    final_answer: str
    _pending_events: list[DomainEvent]
```

### 4.3 AskState (Ask Mode)

```python
class AskState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    memory_context: list[dict[str, Any]]
    final_answer: str
```

---

## 5. Key Interfaces

### 5.1 NoeAgent

```python
class NoeAgent(BaseGraphicAgent):
    def __init__(self, config: AlithiaConfig | None = None) -> None:
        self.config = config or AlithiaConfig()
        super().__init__(
            llm_provider=self.config.llm_provider,
            model_name=self.config.model_name,
        )
        self._memory_manager: MemoryManager | None = None
        self._tool_executor: ToolExecutor | None = None
        self._tool_registry: ToolRegistry | None = None
        self._event_store: EventStore | None = None

    async def initialize(self) -> None:
        """Set up memory, tools, and event infrastructure."""
        ...

    def get_state_class(self) -> Type:
        if self.config.mode == AlithiaMode.ASK:
            return AskState
        return AgentState

    def _build_graph(self) -> StateGraph:
        if self.config.mode == AlithiaMode.ASK:
            return self._build_ask_graph()
        return self._build_agent_graph()

    def run(self, user_message: str, context=None, config=None) -> str:
        """Synchronous entry point."""
        ...

    async def arun(self, user_message: str, context=None) -> str:
        """Async entry point."""
        ...

    async def stream(self, user_message: str, context=None) -> AsyncGenerator[str, None]:
        """Streaming entry point for incremental output."""
        ...
```

### 5.2 TaskPlanner

```python
class TaskPlanner:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self._llm = llm_client

    async def create_plan(self, goal: str, context: str = "") -> TaskPlan:
        """Decompose a goal into a TaskPlan with ordered steps."""
        ...

    async def revise_plan(
        self, plan: TaskPlan, feedback: str, completed_results: list[str],
    ) -> TaskPlan:
        """Revise a plan based on reflection and completed results."""
        ...
```

---

## 6. Implementation Details

### 6.1 Ask Mode Graph

```
START → recall_memory → generate_answer → END
```

**Nodes**:

1. **recall_memory**: Queries MemoryManager with the user's question across all providers. Populates `memory_context` in state.

2. **generate_answer**: Calls LLM with system prompt + memory context + user query. Produces `final_answer`. No tool calls.

**Constraints**: No tools, no writes, no side effects. Pure LLM inference + memory recall.

### 6.2 Agent Mode Graph

```
START → plan → execute_step → [conditional]
  → tool_node → execute_step (loop)
  → reflect → [conditional]
    → revise_plan → execute_step (continue)
    → finalize → END
```

**Nodes**:

1. **plan**: Uses TaskPlanner to decompose the user's request into a TaskPlan. Stores plan in state.

2. **execute_step**: Takes the current step from the plan. Calls LLM with tools available, the current step description, and prior results. LLM either generates a tool call or a text response.

3. **tool_node**: Executes tool calls via ToolExecutor. Collects results. Emits `tool.invoked` / `tool.completed` events.

4. **reflect**: Every `reflection_interval` iterations, the LLM reflects on progress: what's been accomplished, what's remaining, whether the plan needs revision.

5. **revise_plan**: If reflection indicates the plan needs changes, calls TaskPlanner.revise_plan() with feedback.

6. **finalize**: Generates the final comprehensive answer from all accumulated results and reasoning.

**Edges (conditional routing)**:

```python
def _route_after_execute(state: AgentState) -> str:
    if state["plan"] and state["plan"].is_complete:
        return "finalize"
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tool_node"
    if state["iteration"] % config.reflection_interval == 0:
        return "reflect"
    return "execute_step"

def _route_after_reflect(state: AgentState) -> str:
    if "REVISE" in state["reflection"]:
        return "revise_plan"
    if state["plan"] and state["plan"].is_complete:
        return "finalize"
    return "execute_step"
```

### 6.3 Tool Integration

NoeAgent initializes tools via the ToolRegistry (RFC-2004):

```python
async def _setup_tools(self) -> None:
    self._tool_registry = ToolRegistry()

    # Load built-in toolkits
    for toolkit_name in self.config.enabled_toolkits:
        try:
            toolkit = ToolkitRegistry.create_toolkit(toolkit_name)
            tools = BuiltinAdapter.from_toolkit(toolkit, toolkit_name)
            self._tool_registry.register_many(tools)
        except Exception as e:
            self.logger.warning(f"Failed to load toolkit {toolkit_name}: {e}")

    # Load MCP server tools
    for mcp_config in self.config.mcp_servers:
        session = await MCPSession.connect(**mcp_config)
        await self._tool_registry.load_mcp_server(session)

    # Load user-defined tools
    for func in self.config.custom_tools:
        tool = FunctionAdapter.from_function(func)
        self._tool_registry.register(tool)

    # Create ToolExecutor
    self._tool_executor = ToolExecutor(
        event_store=self._event_store,
        producer=AgentRef(agent_id=self._agent_id, agent_type="noe"),
    )
```

In the tool_node, execution is wrapped:

```python
async def _tool_node(self, state: AgentState) -> dict:
    tool_calls = state["messages"][-1].tool_calls
    results = []
    context = ToolContext(
        agent_id=self._agent_id,
        trace=TraceContext(),
        granted_permissions=[ToolPermission(p) for p in self.config.permissions],
        working_directory=self.config.working_directory,
    )
    for call in tool_calls:
        tool = self._tool_registry.get_by_name(call["name"])
        result = await self._tool_executor.run(tool, context, **call["args"])
        results.append({"tool": call["name"], "result": result})

    return {
        "tool_results": results,
        "messages": [ToolMessage(content=str(r["result"]), tool_call_id=call["id"])
                     for r, call in zip(results, tool_calls)],
        "iteration": state["iteration"] + 1,
    }
```

### 6.4 Memory Integration

NoeAgent uses MemoryManager (RFC-2002) for both modes:

**Ask Mode**: recall only (read)
```python
async def _recall_memory_node(self, state: AskState) -> dict:
    query = RecallQuery(query=state["messages"][-1].content, scope=RecallScope.ALL, limit=10)
    results = await self._memory_manager.recall(query)
    return {"memory_context": [{"key": r.entry.key, "value": r.entry.value,
                                 "score": r.score} for r in results]}
```

**Agent Mode**: recall + persist
```python
async def _persist_results(self, key: str, value: str, content_type: str = "research") -> None:
    if self.config.persist_memory:
        await self._memory_manager.store(
            key=key, value=value, content_type=content_type,
            tier=MemoryTier.PERSISTENT,
        )
```

### 6.5 Iteration Control

The agent graph enforces `max_iterations` to prevent infinite loops:

```python
def _should_continue(self, state: AgentState) -> bool:
    if state["iteration"] >= self.config.max_iterations:
        return False
    if state.get("plan") and state["plan"].is_complete:
        return False
    return True
```

---

## 7. Error Handling

### 7.1 Error Types

```python
class AlithiaError(NoesiumError):
    """Base NoeAgent error."""

class PlanningError(AlithiaError):
    """Task planning or revision failed."""

class ModeError(AlithiaError):
    """Invalid mode or mode-specific constraint violation."""

class IterationLimitError(AlithiaError):
    """Max iterations exceeded."""
```

### 7.2 Error Handling Strategy

| Error Category | Handling Approach |
|----------------|-------------------|
| Tool execution failure | Log, add error to tool_results, continue to next step |
| LLM call failure | Retry up to 3 times, then raise |
| Planning failure | Fall back to single-step "just answer" plan |
| Memory recall failure | Continue without memory context, log warning |
| Iteration limit | Force finalize with partial results |
| Permission denied | Skip tool, add error message, continue |

---

## 8. Configuration

### 8.1 Defaults

| Option | Default | Description |
|--------|---------|-------------|
| `mode` | `agent` | Operating mode |
| `max_iterations` | `25` | Maximum graph iterations |
| `max_tool_calls_per_step` | `5` | Max tool calls per execute_step |
| `reflection_interval` | `3` | Steps between reflections |
| `enabled_toolkits` | `["search","bash","python_executor","file_edit"]` | Active toolkits |
| `persist_memory` | `true` | Persist agent results to durable memory |
| `permissions` | `["fs:read","fs:write","net:outbound","shell:execute"]` | Granted tool permissions |

### 8.2 Ask Mode Overrides

When `mode=ask`, the following are forced:
- `max_iterations = 1`
- `enabled_toolkits = []` (no tools)
- `permissions = []` (read-only)
- `persist_memory = false`

---

## 9. Testing Strategy

### 9.1 Unit Tests

| Component | Test Focus |
|-----------|------------|
| `AlithiaConfig` | Defaults, validation, ask mode overrides |
| `TaskPlanner` | Plan creation, revision (with mocked LLM) |
| `AskState` / `AgentState` | State initialization, type safety |
| `_recall_memory_node` | Memory recall with mocked MemoryManager |
| `_tool_node` | Tool execution with mocked ToolExecutor |
| `_route_after_execute` | Conditional routing logic |
| `_route_after_reflect` | Reflection routing logic |

### 9.2 Integration Tests

| Test | Coverage |
|------|----------|
| Ask mode end-to-end | Query → memory recall → LLM answer |
| Agent mode single step | Query → plan → one tool call → finalize |
| Agent mode multi-step | Query → plan → multiple iterations → reflect → finalize |
| Tool failure recovery | Tool fails → agent continues → produces result |
| Memory persistence | Agent writes results → recall in new session |

### 9.3 Test Utilities

```python
class MockLLMClient:
    """Returns pre-configured responses for deterministic testing."""

class MockToolExecutor:
    """Records tool calls and returns pre-configured results."""

class MockMemoryManager:
    """In-memory provider for testing recall and persistence."""
```

---

## 10. Migration / Compatibility

### 10.1 Relationship to Existing Agents

NoeAgent does NOT replace existing agents (AskuraAgent, SearchAgent, DeepResearchAgent). It is a new agent that leverages the unified tool and memory systems.

### 10.2 Incremental Adoption

1. **Phase 1**: NoeAgent with ask mode using existing LLM client and basic memory.
2. **Phase 2**: Agent mode with built-in toolkits and TaskPlanner.
3. **Phase 3**: MCP tool integration and memory persistence.
4. **Phase 4**: Streaming output and advanced reflection.

---

## Appendix A: RFC Requirement Mapping

| RFC Requirement | Guide Section | Implementation |
|-----------------|---------------|----------------|
| RFC-1002 §5.2 (Conversation Agent) | §6.1 | Ask mode graph |
| RFC-1002 §5.3 (Research Agent) | §6.2 | Agent mode graph |
| RFC-1002 §5.4 (Task Agent) | §6.2 | TaskPlanner + agent loop |
| RFC-2001 §9 (Recall Protocol) | §6.4 | MemoryManager.recall() |
| RFC-2002 §8 (MemoryManager) | §6.4 | Memory store/recall |
| RFC-2003 §7 (Event-Wrapped Execution) | §6.3 | ToolExecutor.run() |
| RFC-2004 §5 (ToolExecutor) | §6.3 | Tool node implementation |
| RFC-2004 §7 (Source Adapters) | §6.3 | _setup_tools() |
| RFC-0003 §10 (Checkpointing) | §6.5 | Iteration control |

---

## Appendix B: Revision History

| Date | RFC Version | Changes |
|------|-------------|---------|
| 2026-03-01 | Initial | Initial guide based on RFC-1002, RFC-2001-2004 |
