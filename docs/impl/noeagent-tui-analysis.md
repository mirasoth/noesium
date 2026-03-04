# NoeAgent TUI Design Analysis

> Analysis of the current Rich-based TUI implementation, gap assessment against
> target requirements, and design proposals for subagent-aware progress display.
>
> **Module**: `noesium/noeagent/tui.py` (818 lines)
> **Agent**: `noesium/noeagent/agent.py` (556 lines)
> **Progress**: `noesium/noeagent/progress.py` (76 lines)
> **Design Principle**: Simple but strong to use in practice

---

## 1. Current Feature Inventory

### 1.1 Live Plan Table

| Component | Location | Description |
|-----------|----------|-------------|
| `render_plan_table()` | `tui.py:129-153` | Builds `rich.Table` from `TaskPlan`. Columns: `#`, `Status`, `Step`. Status markers: `[ ]` pending, `[>]` in_progress (yellow), `[✓]` completed (green), `[✗]` failed (red). |
| `render_compact_progress()` | `tui.py:156-179` | One-line summary: `✓ 2/3 · Step description`. Shows completed/total count with current step truncated to 60 chars. |
| Plan in `_build_display()` | `tui.py:528-536` | Both compact progress and full plan table rendered in the live display group. Plan table is always shown when a plan exists. |

### 1.2 Step Progress Details

| Feature | Location | Rendering |
|---------|----------|-----------|
| Plan created | `tui.py:558-559` | `📋 Plan created with N steps` (dim) |
| Plan revised | `tui.py:565` | `📝 Plan revised` (dim) |
| Step start | `tui.py:575-577` | `[>] Step N: description` (yellow) |
| Step complete | `tui.py:584-588` | `[✓] Step N: description` (green) |
| Tool use | `tui.py:601-602` | `→ Using tool: tool_name` (blue) |
| Reflection | `tui.py:633` | `💭 Reflection completed` (dim italic) |
| Final answer | `tui.py:644` | `✓ Final answer generated` (bold green) |
| Display cap | `tui.py:539` | Last 5 step details shown in live display |

### 1.3 Activity Lines

| Feature | Location | Description |
|---------|----------|-------------|
| `_activity_line()` | `tui.py:187-229` | Maps `ProgressEvent` to compact `Text`. Handles: `TOOL_START` (blue), `TOOL_END` (green + brief result), `SUBAGENT_START` (bold magenta), `SUBAGENT_PROGRESS` (magenta), `SUBAGENT_END` (green), `THINKING` (dim italic), `ERROR` (red). |
| Display cap | `tui.py:542` | Last 15 activity lines shown in live display |

### 1.4 Dynamic Thinking Spinner

| Component | Location | Description |
|-----------|----------|-------------|
| `DynamicThinkingText` | `tui.py:82-114` | Rotates messages every 1.5s based on phase. Phases: `planning`, `executing`, `reflecting`, `finalizing`, `tool_use`, `default`. |
| `THINKING_MESSAGES` | `tui.py:33-67` | 4 messages per phase, cycled round-robin. |
| Spinner | `tui.py:520-522` | `Spinner("dots")` with dynamic text, cyan style. Always last element in live display. |
| Phase mapping | `tui.py:607-618` | THINKING events update phase via keyword matching on `event.summary`. |

### 1.5 Live Display Composition

`_build_display()` assembles a `Group` of renderables refreshed at 8fps in two blocks (see **§4. TUI Output Layout**):

- **Block A – Streaming progress**: Subagent tracks (`sa_tracker.render()`), then activity lines (last 15). Step details (Plan created, o N/M · Step K/M, → Using tool, etc.) are not shown in the live display.
- **Block B – Persistent plan**: Main plan tree, subagent plan trees (if any), then spinner.

```
┌──────────────────────────────────────┐
│   [browser_use] + 2/5 · step desc     │  ← subagent tracks
│   . Using tool(...)                   │  ← activity lines (last 15)
│   > web_search  result snippet...    │
│                                      │
│   Plan: goal                          │  ← plan tree
│   ├── [>] First step                  │
│   ├── [+] Second step                 │
│   └── [ ] Third step                  │
│                                      │
│ ⠋ Processing...                      │  ← spinner
└──────────────────────────────────────┘
```

The `Live` context uses `transient=True` so the live display is replaced by static post-processing output after completion.

### 1.6 Post-Processing Output

After the live display exits (`tui.py:654-671`):
1. Static plan table rendered with final statuses
2. Partial results rendered as Markdown (with `Rule` separators)
3. Final answer rendered as Markdown

### 1.7 ProgressEventType Coverage

| Event Type | Emitted By | TUI Handles | Notes |
|------------|------------|-------------|-------|
| `SESSION_START` | `agent.py:518` | No (ignored) | Start marker for logging |
| `SESSION_END` | `agent.py:711` | Yes (`tui.py:646-652`) | Marks all steps completed |
| `PLAN_CREATED` | `agent.py:538` | Yes (`tui.py:554-559`) | Updates plan + step details |
| `PLAN_REVISED` | `agent.py:538` | Yes (`tui.py:561-565`) | Updates plan + step details |
| `STEP_START` | `agent.py:578-586` | Yes (`tui.py:567-577`) | Updates plan step status + step details |
| `STEP_COMPLETE` | `agent.py:566-574` | Yes (`tui.py:579-588`) | Updates plan step status + step details |
| `TOOL_START` | `agent.py:624-633` | Yes (activity + step details) | Blue activity line + tool arrow |
| `TOOL_END` | `agent.py:596-605` | Yes (activity line) | Green activity line with result |
| `SUBAGENT_START` | `agent.py:640-648` | Yes (activity line) | Bold magenta, from `additional_kwargs` |
| `SUBAGENT_PROGRESS` | **Never emitted** | Yes (handler exists) | Handler at `tui.py:215-217`, but no event source |
| `SUBAGENT_END` | **Never emitted** | Yes (handler exists) | Handler at `tui.py:219-221`, but no event source |
| `THINKING` | `agent.py:540-550,617-623,662-668,685-688` | Yes (activity + phase) | Phase-based mapping |
| `TEXT_CHUNK` | `agent.py:650-657` | No (`tui.py:628`, pass) | Ignored in TUI |
| `PARTIAL_RESULT` | Not currently emitted | Yes (`tui.py:623-625`) | Collected for post-processing |
| `REFLECTION` | `agent.py:669-677` | Yes (activity + step details) | Dim italic |
| `FINAL_ANSWER` | `agent.py:689-697` | Yes (`tui.py:635-644`) | Marks plan complete, step detail |
| `ERROR` | `agent.py:699-706` | Yes (activity line) | Red error message |

### 1.8 Slash Commands

| Command | Location | Action |
|---------|----------|--------|
| `/exit`, `/quit` | `tui.py:261-263` | Exit TUI |
| `/help` | `tui.py:265-271` | Show command table |
| `/mode ask\|agent` | `tui.py:274-281` | Switch agent mode |
| `/plan` | `tui.py:283-287` | Show current plan table |
| `/memory` | `tui.py:289-300` | Show memory stats (JSON panel) |
| `/session` | `tui.py:302-306` | Show session log path |
| `/clear` | `tui.py:311-312` | Clear screen |

### 1.9 Input System

| Component | Location | Description |
|-----------|----------|-------------|
| `InputHistory` | `tui.py:324-391` | JSON-persisted command history with configurable max size. |
| `read_user_input()` | `tui.py:394-485` | Primary: `prompt_toolkit.PromptSession` with `InMemoryHistory` pre-populated from `InputHistory`. Fallback: `rich.prompt.Prompt`. Backslash continuation for multiline. |
| Ctrl+C handling | `tui.py:686-691,762-770` | First press during execution cancels task. Second press within 2s exits TUI. |

### 1.10 Main Loop

`run_agent_tui()` at `tui.py:679-774`:
- Creates `asyncio.new_event_loop()` and runs queries via `loop.run_until_complete()`
- Manages `SessionLogger` registration into `progress_callbacks`
- Handles slash commands before query processing
- Double Ctrl+C exit pattern

---

## 2. Gap Analysis

### 2.1 Subagent Progress is Opaque

**Current state**: When the parent agent delegates to a child via `interact_with_subagent()` (`agent.py:756-759`), it calls `child.arun()` which internally iterates `child.astream_progress()` but only returns the final answer string. The parent's progress stream receives `SUBAGENT_START` (from `additional_kwargs` parsing at `agent.py:636-648`) but **never** `SUBAGENT_PROGRESS` or `SUBAGENT_END`.

The `spawn_subagent` tool function (`agent.py:219-228`) also calls `interact_with_subagent()`, so tool-based subagent invocation has the same opacity.

**Impact**: The TUI shows a subagent spawn line but then goes silent until the subagent finishes — which could be minutes for complex tasks. Library consumers face the same blind spot.

### 2.2 No Async/Concurrent Subagent Tracking

**Current state**: Subagents execute sequentially. `interact_with_subagent()` is `await`-ed directly, blocking the parent's LangGraph execution. If a plan step requires multiple subagents, they run one after another.

The TUI has no concept of concurrent progress tracks. Activity lines are interleaved in a flat list with no grouping by subagent.

**Impact**: Slower execution for parallelizable tasks, and confusing TUI output if interleaving were to happen.

### 2.3 Library Mode Consistency Gap

**Current state**: `astream_progress()` is the canonical event source for both TUI and library mode. The TUI does not maintain any state outside of what `ProgressEvent` provides — all plan updates, step statuses, and tool activities derive from events. This is good.

**Gap**: Since `SUBAGENT_PROGRESS` and `SUBAGENT_END` are never emitted, both TUI and library consumers share the same visibility gap. The fix must happen at the `agent.py` level (event emission), not the `tui.py` level (rendering).

### 2.4 MCP/Skill Metadata Loss

**Current state**: MCP tools are invoked through `CapabilityRegistry` providers, which use `ToolExecutor`. The executor emits rich domain events (`ToolInvoked`, `ToolCompleted`, `ToolFailed`, `ToolTimeout`) to `EventStore` with fields like `duration_ms`, `correlation_id`, etc. However, NoeAgent's progress stream only captures tool invocations from LLM `tool_calls` messages — not from executor-level events.

**Impact**: Basic tool start/end display works fine. But richer metadata (MCP server name, execution latency, retry info) is available in `EventStore` but not surfaced to the TUI or library consumers.

### 2.5 No Error Recovery Display

**Current state**: `ProgressEventType.ERROR` is emitted on exception and rendered as a red activity line. However, there is no retry indicator, no error-then-recovery display, and failed steps in the plan table are not visually distinguished from pending ones during execution (the plan's step status is only set by node outputs, not by error events).

---

## 3. Design Proposals

### 3.1 Subagent Progress Propagation

**Goal**: Child agent events flow to parent's progress stream and callbacks.

#### Agent-Side Changes (`agent.py`)

Replace the opaque `interact_with_subagent()` with a streaming variant:

```python
async def interact_with_subagent(self, subagent_id: str, message: str) -> str:
    child = self._subagents[subagent_id]
    final_answer = ""
    async for event in child.astream_progress(message):
        # Re-emit child events as SUBAGENT_PROGRESS on parent
        if event.type == ProgressEventType.FINAL_ANSWER:
            final_answer = event.text or ""
        elif event.type not in (
            ProgressEventType.SESSION_START,
            ProgressEventType.SESSION_END,
        ):
            wrapped = ProgressEvent(
                type=ProgressEventType.SUBAGENT_PROGRESS,
                session_id=event.session_id,
                sequence=event.sequence,
                subagent_id=subagent_id,
                summary=f"[{subagent_id}] {event.summary or ''}",
                detail=event.detail,
                metadata={
                    "child_event_type": event.type.value,
                    "child_node": event.node,
                    **event.metadata,
                },
            )
            await self._fire_callbacks(wrapped)
    # Emit SUBAGENT_END
    end_event = ProgressEvent(
        type=ProgressEventType.SUBAGENT_END,
        subagent_id=subagent_id,
        summary=f"[{subagent_id}] completed",
    )
    await self._fire_callbacks(end_event)
    return final_answer
```

**Key design decisions**:
- Child `SESSION_START`/`SESSION_END` are suppressed (they are parent-level concepts)
- All other child events wrapped as `SUBAGENT_PROGRESS` with original type preserved in `metadata.child_event_type`
- Parent callbacks receive events in real-time as the child progresses
- Library consumers using `astream_progress()` also need the wrapped events yielded — this requires the `astream_progress()` method to also integrate with a callback-to-yield bridge (see 3.4)

#### TUI-Side Changes (`tui.py`)

The existing `_activity_line()` handlers for `SUBAGENT_START`, `SUBAGENT_PROGRESS`, and `SUBAGENT_END` are already implemented and correctly styled. The only addition needed:

- In `_process_query()`, handle `SUBAGENT_PROGRESS` events to update step details:

```python
elif etype == ProgressEventType.SUBAGENT_PROGRESS:
    line = _activity_line(event, thinking_gen)
    if line:
        activity_lines.append(line)
    child_type = (event.metadata or {}).get("child_event_type", "")
    if child_type == "plan.created":
        step_details.append(
            Text.assemble(("    ", ""), (f"[{event.subagent_id}] ", "magenta"), ("Plan created", "dim"))
        )
```

### 3.2 Async Subagent Display

**Goal**: Track multiple subagents concurrently with distinct visual sections.

#### SubagentTracker

A lightweight state tracker in `tui.py`:

```python
@dataclass
class SubagentState:
    subagent_id: str
    status: str  # "running" | "done" | "error"
    plan_steps: int = 0
    completed_steps: int = 0
    current_step: str = ""
    last_activity: str = ""

class SubagentTracker:
    def __init__(self, max_display: int = 3):
        self._states: dict[str, SubagentState] = {}
        self._max_display = max_display

    def update(self, event: ProgressEvent) -> None:
        sid = event.subagent_id or return
        if sid not in self._states:
            self._states[sid] = SubagentState(subagent_id=sid, status="running")
        state = self._states[sid]
        child_type = (event.metadata or {}).get("child_event_type", "")
        # Update state based on child event type...

    def render(self) -> list[Text]:
        """Render compact subagent status lines."""
        lines = []
        for state in list(self._states.values())[-self._max_display:]:
            if state.status == "done":
                lines.append(Text.assemble(
                    (f"  [{state.subagent_id}] ", "green"),
                    (f"✓ {state.completed_steps}/{state.plan_steps} done", "green"),
                ))
            else:
                lines.append(Text.assemble(
                    (f"  [{state.subagent_id}] ", "magenta"),
                    (f"> {state.completed_steps}/{state.plan_steps} · {state.current_step[:40]}", "yellow"),
                ))
        return lines
```

The `_build_display()` function includes `subagent_tracker.render()` between step details and activity lines, showing at most 3 concurrent subagent tracks.

### 3.3 Consistency Contract

The canonical data flow for all consumers:

```
NoeAgent.astream_progress()
    ├─ yield ProgressEvent  ──→  TUI (_process_query async for loop)
    ├─ _fire_callbacks()    ──→  SessionLogger.on_progress() → JSONL
    └─ _fire_callbacks()    ──→  Library push-style callbacks
```

**Rules**:
1. `astream_progress()` is the single source of truth for all event types
2. Every event yielded by `astream_progress()` is also sent to `_fire_callbacks()`
3. The TUI renders **only** from `ProgressEvent` fields — no side-channel state
4. `SessionLogger` captures the identical event sequence for offline replay
5. Subagent events must flow through the same path: yielded by parent's `astream_progress()` **and** sent to parent's `_fire_callbacks()`

**Current deviation**: The proposed `interact_with_subagent()` calls `_fire_callbacks()` for child events, but the parent's `astream_progress()` generator does not yield those events (they happen inside `subagent_node` execution). This requires a callback-to-yield bridge.

### 3.4 Callback-to-Yield Bridge for Subagent Events

The `astream_progress()` generator needs to yield events that are emitted by nested code (like `interact_with_subagent` running inside `subagent_node`). Since `astream_progress()` iterates `compiled.astream()`, it only sees node outputs — not intermediate events fired inside nodes.

**Solution**: Use an `asyncio.Queue` as a bridge:

```python
async def astream_progress(self, user_message, context=None):
    event_queue = asyncio.Queue()
    original_fire = self._fire_callbacks

    async def _bridged_fire(event):
        await original_fire(event)
        await event_queue.put(event)

    self._fire_callbacks = _bridged_fire
    try:
        # Drain queue between astream iterations
        async for raw_event in compiled.astream(initial):
            # ... existing node output processing ...
            # Drain any queued subagent events
            while not event_queue.empty():
                queued_evt = event_queue.get_nowait()
                yield queued_evt
    finally:
        self._fire_callbacks = original_fire
```

This ensures subagent progress events are yielded to TUI consumers while also reaching push-style callbacks.

---

## 4. TUI Output Layout (Streaming vs Persistent Plan)

**Goal**: Match a clear two-block layout: streaming progress first, then the persistent plan and spinner. No section headers in the UI (any "## ..." in examples are 提示词 only).

### 4.1 Desired Layout

```text
noe|agent> <prompt>

  [browser_use] > Browser step 13/15
  [browser_use] > Browser action
  [browser_use] + Action completed
  ...
  [browser_use] Browser task completed
  [browser_use] completed
  > subagent:browser_use  <result summary>

  Plan: <goal>
  ├── [>] step 1
  └── [ ] step 2

  <spinner>
```

### 4.2 Live Display Order (`_build_display()`)

- **Block A – Streaming progress** (no section header): `sa_tracker.render()` then `activity_lines` (last 15). All subagent/activity lines appear together.
- **Block B – Persistent plan** (no section header): Main plan tree, subagent plan trees (if any), then spinner.

**step_details** (Plan created, o N/M · Step K/M, → Using tool, [tag] Plan created, Reflection, etc.) are **omitted from the live display** (Option A) so the streaming block shows only subagent/activity lines; the plan tree already conveys the plan.

### 4.3 Deduplication

- **"Plan created with N steps"**: Append at most once per run (e.g. only on first `PLAN_CREATED` when `current_plan` becomes non-None).
- **"[tag] Plan created"**: Append at most once per subagent (e.g. do not append again if `subagent_plans` already has that tag).

### 4.4 Post-Live

Plan tree(s), then partial_results, then final_answer. No section headers. Optionally reprint last K activity lines above the plan tree for consistency.

### 4.5 Reference

- Plan: TUI output layout sections (streaming block first, plan block second, no headers, dedup).
- Module: `noesium/noeagent/tui.py` — `_build_display()`, PLAN_CREATED/SUBAGENT_PROGRESS handling.

---

## 5. Implementation Roadmap

### Phase 1: Subagent Event Emission (agent.py)

**Scope**: Replace `interact_with_subagent()` to stream child events.

**Changes**:
- `agent.py`: Rewrite `interact_with_subagent()` to iterate `child.astream_progress()` and emit `SUBAGENT_PROGRESS`/`SUBAGENT_END` via `_fire_callbacks()`
- `agent.py`: Add callback-to-yield bridge in `astream_progress()` so subagent events are yielded
- `progress.py`: No changes needed (event types already exist)

**Validation**: Library mode test — assert `SUBAGENT_PROGRESS` and `SUBAGENT_END` events appear in the stream when a subagent is used.

### Phase 2: TUI Subagent Display (tui.py)

**Scope**: Visual subagent tracking in the live display.

**Changes**:
- `tui.py`: Add `SubagentTracker` class
- `tui.py`: Update `_process_query()` to feed subagent events into tracker
- `tui.py`: Update `_build_display()` to include tracker rendering
- `tui.py`: Update `_activity_line()` if richer child event detail is needed

**Validation**: Manual TUI testing with a subagent-spawning query. Verify bracketed progress lines appear and update in real-time.

### Phase 3: Concurrent Subagent Execution (agent.py, nodes.py)

**Scope**: Allow parallel subagent execution for independent subtasks.

**Changes**:
- `nodes.py`: Add support for batched subagent actions (multiple `SubagentAction` in one step)
- `agent.py`: Use `asyncio.gather()` for parallel `interact_with_subagent()` calls
- `tui.py`: Handle interleaved events from multiple concurrent subagents via `SubagentTracker`
- `planner.py`: Enable planner to mark steps as parallelizable

**Validation**: Test with a query requiring 2+ independent subagents. Verify parallel execution and correct multiplexed display.

---

## 6. Design Principles Summary

| Principle | How It's Applied |
|-----------|-----------------|
| Simple but strong | Flat `ProgressEvent` model with `summary` for display, `detail` for logging. No complex TUI framework — just Rich `Live` + `Group`. |
| Library-first | All progress flows through `astream_progress()`. TUI is a consumer, not a special case. |
| Subagent transparency | Child events wrapped and forwarded. Same visibility in TUI and library mode. |
| Bounded display | Last 5 step details, last 15 activity lines, max 3 subagent tracks. Prevents clutter. |
| Graceful degradation | prompt_toolkit optional (falls back to Rich Prompt). Subagent progress optional (falls back to start/end only). |
