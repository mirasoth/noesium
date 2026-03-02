# NoeAgent: Tool Calls vs Subagent Calls

> Implementation guide comparing the two execution modalities available to NoeAgent.
>
> **Module**: `noesium/noe/`
> **Source**: Derived from [RFC-0005](../../specs/RFC-0005.md) §16 (Tool vs Subagent Capabilities)
> **Companion**: [noe-agent-impl.md](noe-agent-impl.md)

---

## 1. Purpose

NoeAgent can fulfill plan steps using either **tool calls** or **subagent calls**. This guide defines the architectural distinction, decision heuristics, and implementation mapping for each path.

---

## 2. Ontological Distinction

| Dimension | Tool Call | Subagent Call |
|-----------|----------|---------------|
| Nature | Function / procedure | Cognitive worker |
| Identity | Stateless capability | Stateful actor |
| Abstraction Level | Procedure | Reasoning entity |
| Role | Execute | Think + Execute |

A **tool** is an extension of NoeAgent's capability.
A **subagent** is an extension of NoeAgent's cognition.

---

## 3. Control Model

### Tool

Caller retains full control. The tool does not decide what to do next.

```
execute_step → AgentAction.tool_calls → tool_node → ToolMessage → execute_step
```

- Deterministic (given same input → same output)
- Single-turn
- NoeAgent owns all reasoning
- Tool is passive

### Subagent

Delegated autonomy. The subagent is allowed to think inside its boundary.

```
execute_step → AgentAction.subagent → subagent_node
                                        ↳ child.arun() → internal loop
                                        ↳ child tool usage
                                        ↳ child planning
                                      → result → execute_step
```

- Multi-step internal loop
- May plan internally
- May call tools
- Owns partial reasoning space

---

## 4. State and Memory

| Aspect | Tool | Subagent |
|--------|------|----------|
| Stateful | No | Yes |
| Session Memory | None | Persistent (within session) |
| Cross-call continuity | No | Yes |
| Internal scratchpad | No | Yes |

**Design invariant**: Tools must be referentially transparent when possible. Subagents are intentionally not.

External CLI daemons (§5.10 in impl guide) amplify this distinction -- they maintain process-level state across multiple task dispatches.

---

## 5. Temporal Scope

### Tool

- Instantaneous (bounded execution time)
- Blocking (from NoeAgent's perspective)
- Request-response atomic

### Subagent

- Long-lived (may run for minutes)
- May be asynchronous
- Can be BUSY / IDLE
- Owns its own lifecycle

This difference impacts scheduler design, resource accounting, and failure recovery.

---

## 6. Failure Semantics

| Aspect | Tool | Subagent |
|--------|------|----------|
| Crash impact | Single request | Session-level |
| Recovery | Retry call | Restart process |
| State loss | None (stateless) | Possible |
| Health monitoring | Optional | Mandatory (CLI daemons) |

Subagents require heartbeat, liveness detection, and restart strategy. Tools do not.

---

## 7. Scheduling Philosophy

### Tool = Cheap Primitive

- Spawn per call, no lifecycle management
- No queuing needed
- Parallelizable (multiple `ToolCallAction` in one `AgentAction`)
- Resource cost: negligible

### Subagent = Heavy Worker

- Reuse instance across tasks
- Task queue per instance
- Concurrency policy required
- Resource cost: significant (LLM tokens, process memory)

---

## 8. NoeAgent Decision Matrix

When `TaskStep.execution_hint` is `"auto"`, the planner and LLM use these heuristics:

| Signal | Route to | Example |
|--------|----------|---------|
| Single atomic operation | **Tool** | `web_search("python asyncio")` |
| Read/write a file | **Tool** | `file_edit.read_file("config.py")` |
| Run a shell command | **Tool** | `bash.run_bash("ls -la")` |
| Multi-step research with synthesis | **Subagent** | "Analyze the auth module" |
| Independent parallel subtasks | **Multiple subagents** | "Search 3 databases concurrently" |
| Task requiring persistent code context | **CLI subagent** | "Refactor the payment module" |
| Specialized external agent capability | **CLI subagent** | "Claude: review for security issues" |
| Simple computation | **Tool** | `python_executor("sum(range(100))")` |
| Complex analysis needing planning | **Subagent** | "Compare 5 frameworks and recommend" |
| Latency-sensitive, low complexity | **Tool** | Quick search/lookup |
| Quality-sensitive, high complexity | **Subagent** | Deep research/analysis |

---

## 9. Implementation Mapping

### 9.1 AgentAction Schema

```python
class AgentAction(BaseModel):
    thought: str
    tool_calls: list[ToolCallAction] | None = None
    subagent: SubagentAction | None = None
    text_response: str | None = None
    mark_step_complete: bool = False
```

Exactly one of `tool_calls`, `subagent`, or `text_response` must be set (enforced by `model_validator`).

### 9.2 Routing in _route_after_execute

```python
def _route_after_execute(self, state: AgentState) -> str:
    if plan.is_complete: return "finalize"
    if last_msg has tool_calls: return "tool_node"
    if last_msg has subagent_action: return "subagent_node"
    if iteration >= max: return "finalize"
    if reflection_due: return "reflect"
    return "execute_step"
```

### 9.3 tool_node Implementation

```
For each ToolCallAction:
  1. Pre-validate args against tool.input_schema
  2. Apply type coercion if needed
  3. Dispatch via ToolExecutor.run()
  4. Collect result as ToolMessage
  5. Enforce max_tool_calls_per_step limit
```

### 9.4 subagent_node Implementation

```
Read subagent_action from last message:
  spawn → NoeAgent child (in-process) or ExternalCliAdapter.spawn()
  interact → child.arun() or adapter.send()
  spawn_cli → ExternalCliAdapter.spawn(CliSubagentConfig)
  interact_cli → adapter.send(handle, message)
  terminate_cli → adapter.terminate(handle)
```

### 9.5 Subagent-as-Tool Fallback

When `enable_subagents=True`, a `spawn_subagent(name, task, mode)` function is registered as a regular tool. This allows the LLM to use the standard tool-calling path even for subagent tasks. `tool_node` also intercepts `tool_name="subagent"` and redirects to `spawn_subagent`.

---

## 10. Anti-Patterns

These patterns indicate architectural confusion between tools and subagents:

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| Hidden state in tools | Tool maintains internal state across calls | Make tool stateless; use subagent if state needed |
| Unbounded tool runtime | Tool runs for minutes without timeout | Set timeout; consider subagent for long tasks |
| Subagent for trivial ops | Spawning a subagent to read a file | Use tool directly |
| Tool that plans internally | Tool does multi-step reasoning | This is a subagent; model it correctly |
| Single-use subagent for atomic task | Spawn + interact + terminate for one search | Use tool instead |

---

## 11. Cost and Performance Considerations

| Metric | Tool | Subagent |
|--------|------|----------|
| Latency (typical) | 100ms - 10s | 10s - 300s |
| LLM tokens per invocation | 0 (tool itself) | 1000-50000+ (child LLM calls) |
| Memory overhead | None | Child agent state + memory providers |
| Process overhead | None | Child NoeAgent or CLI daemon process |
| Parallelization | Multiple `ToolCallAction` in one step | Multiple `spawn_subagent` calls |

**Guideline**: Use tools by default. Escalate to subagents only when the task requires autonomous multi-step reasoning, persistent state, or specialized external capabilities.

---

## 12. Observability

### Tool

- `TOOL_START` / `TOOL_END` progress events
- Input args and output result logged to session JSONL

### Subagent

- `SUBAGENT_START` / `SUBAGENT_PROGRESS` / `SUBAGENT_END` progress events
- Child agent has its own session log (nested JSONL)
- Internal reasoning trace available in child's session log
- CLI daemon stdout captured by `ExternalCliAdapter`

---

## Appendix: RFC-0005 Alignment

This guide implements the capability type taxonomy from RFC-0005 §4.2:

| RFC-0005 CapabilityType | NoeAgent Mapping |
|------------------------|------------------|
| `InProcessTool` | `ToolCallAction` → `tool_node` → `ToolExecutor` |
| `RemoteTool` | MCP tools loaded via `load_mcp_server` |
| `Subagent` | `SubagentAction(action="spawn")` → in-process NoeAgent child |
| `ExternalCliSubagent` | `SubagentAction(action="spawn_cli")` → `ExternalCliAdapter` daemon |
