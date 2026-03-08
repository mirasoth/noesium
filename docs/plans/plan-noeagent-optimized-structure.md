# NoeAgent Optimized Code Structure (Spec-Aligned)

**Date**: 2026-03-08  
**Status**: Implemented  
**References**: RFC-0001, RFC-1004, RFC-1005, RFC-1006, RFC-1009, RFC-2002, RFC-2004, rfc-namings

---

## 1. Objective

Propose an optimized code structure for the `noeagent` package that:

- Aligns with the **Autonomous Architecture** (RFC-1005): Goal Engine, Cognitive Loop, Agent Kernel, Capability System, Memory System.
- Respects **RFC-1009** (Layered Impl): noeagent as Application Layer depending only on noesium (core, toolkits, subagents).
- Maps cleanly to **RFC-1004** (Kernel + Effect Executor), **RFC-2002** (LangGraph agents), and **RFC-2004** (Tool vs Subagent).
- Fixes structural gaps (e.g. missing `graph/nodes`, kernel vs agent boundary) and reduces duplication.

---

## 2. Spec Mapping

| Spec | Concept | NoeAgent mapping |
|------|---------|------------------|
| RFC-0001 §5.2 | Agent Kernel (graph-based runtime) | LangGraph workflow in `graph/`; step interface in `kernel/` |
| RFC-1004 | Kernel purity; sandboxed effect execution | Tools/subagents via Capability Registry; no direct I/O in kernel |
| RFC-1005 | Five components: Goal Engine, Cognitive Loop, Agent Kernel, Capability System, Memory System | `autonomous/`, `kernel/`, `capabilities/`, memory via noesium.core |
| RFC-1006 | Goal Engine (lifecycle, queue, scheduling) | In noeagent.autonomous (moved from noesium.core.autonomous) |
| RFC-1009 §5.3.4 | Application layer: agent, config, tui, cli_adapter | `agent.py`, `config.py`, `tui.py`, `cli_adapter.py` |
| RFC-2002 | BaseGraphicAgent, state graph, nodes, routing | `graph/builder`, `graph/routing`, graph nodes |
| RFC-2004 | Tool call vs subagent call | `schemas.py` (AgentAction, ToolCallAction, SubagentAction); execution in capabilities |

---

## 3. Current Structure (Summary)

```
noeagent/
├── src/noeagent/
│   ├── __init__.py          # Public API, NOESIUM_HOME, re-exports
│   ├── agent.py             # NoeAgent (BaseGraphicAgent), init, run, graph build
│   ├── config.py            # NoeConfig, NoeMode, toolkit/subagent config
│   ├── schemas.py           # AgentAction, ToolCallAction, SubagentAction
│   ├── state.py             # AgentState, AskState, TaskPlan, TaskStep
│   ├── planner.py           # TaskPlanner (goal → TaskPlan)
│   ├── commands.py          # Inline commands, subagent CLI
│   ├── session_log.py       # Session logging
│   ├── cli_adapter.py       # CLI interface
│   ├── tui.py               # Terminal UI
│   ├── prompts/             # Prompt manager and templates
│   ├── capabilities/        # Tools + subagents setup
│   │   ├── __init__.py
│   │   └── tools.py         # setup_tools, register_subagent_tool
│   ├── graph/               # LangGraph workflow
│   │   ├── __init__.py      # build_*_graph, nodes, routing
│   │   ├── builder.py       # build_ask_graph, build_agent_graph
│   │   └── routing.py       # route_after_execute, route_after_reflect
│   │   # MISSING: nodes.py   # Referenced by builder + __init__ but file absent
│   ├── kernel/              # Agent Kernel (RFC-1005 §8)
│   │   ├── __init__.py      # AgentKernel
│   │   ├── core.py          # AgentKernel(NoeAgent), step(goal, context)->Decision
│   │   └── README.md
│   ├── autonomous/          # Cognitive Loop + runner
│   │   ├── __init__.py
│   │   ├── cognitive_loop.py
│   │   └── runner.py
│   └── legacy/              # Deprecated / migration
│       └── gem_parser.py
├── tests/
└── ...
```

**Gaps:**

- **Missing `graph/nodes.py`**: `graph/builder.py` and `graph/__init__.py` import from `.nodes` (e.g. `plan_node`, `execute_step_node`, `recall_memory_node`, `reflect_node`, `finalize_node`, `subagent_node`, `revise_plan_node`, `generate_answer_node`). Tests reference `noeagent.nodes`. The module is missing and breaks graph build/imports.
- **Missing `capabilities/subagents.py`**: `agent.py` imports `setup_external_subagents` and `setup_builtin_subagents` from `noeagent.capabilities.subagents`, but that module does not exist (only `capabilities/tools.py` is present). Either create `capabilities/subagents.py` with these functions or move the logic currently in `agent.py` (e.g. `_create_browser_use_agent`, `_create_tacitus_agent`, CLI adapter setup) into it so subagent setup lives in one place.
- **Kernel vs Agent**: Kernel correctly wraps NoeAgent and exposes `step()`; ensure no duplicate “orchestration” logic between `agent.py` and `kernel/core.py`.

---

## 4. Proposed Optimized Structure

### 4.1 Directory Layout

```
noeagent/src/noeagent/
├── __init__.py                 # Public API only; NOESIUM_HOME; re-exports
├── agent.py                    # NoeAgent: init, run, graph compilation, mode dispatch
├── config.py                   # NoeConfig, NoeMode, CliSubagentConfig, etc.
├── schemas.py                  # AgentAction, ToolCallAction, SubagentAction (RFC-2004)
├── state.py                    # AgentState, AskState, TaskPlan, TaskStep (graph state)
├── planner.py                  # TaskPlanner (goal → flat TaskPlan; execution hints)
├── commands.py                 # Inline commands, subagent CLI
├── session_log.py              # Session logging
├── cli_adapter.py              # CLI entry
├── tui.py                      # Terminal UI
│
├── kernel/                     # Agent Kernel (RFC-1005 §8) — reasoning step interface
│   ├── __init__.py             # AgentKernel
│   ├── core.py                 # AgentKernel(agent).step(goal, context) -> Decision
│   └── README.md               # Kernel role and integration
│
├── graph/                      # LangGraph as single execution authority (RFC-0001 §5.2)
│   ├── __init__.py             # build_ask_graph, build_agent_graph, routing, nodes (re-export)
│   ├── builder.py              # build_ask_graph, build_agent_graph
│   ├── nodes.py                # All node implementations (ADD MISSING MODULE)
│   └── routing.py              # route_after_execute, route_after_reflect
│
├── capabilities/               # Capability System (RFC-1005 §9) — tools + subagents
│   ├── __init__.py             # Optional: setup_capabilities facade
│   ├── tools.py                # setup_tools, register_subagent_tool, tool descriptions
│   └── subagents.py            # setup_external_subagents, setup_builtin_subagents
│
├── autonomous/                 # Goal Engine, Cognitive Loop, Event System (RFC-1005 §6–7, RFC-1006, RFC-1007)
│   ├── __init__.py             # Goal, GoalEngine, CognitiveLoop, runner, events, event_system, triggers
│   ├── cognitive_loop.py       # CognitiveLoop(goal_engine, memory, agent_kernel, registry)
│   ├── runner.py               # AutonomousRunner, run_autonomous_mode
│   ├── models.py               # Goal, GoalStatus (moved from noesium.core.autonomous)
│   ├── goal_engine.py          # GoalEngine (moved from noesium.core.autonomous)
│   ├── decision_schema.py      # Decision, DecisionAction, *Decision (moved from noesium.core.autonomous)
│   ├── events.py               # GoalCreated, GoalUpdated, GoalCompleted, GoalFailed (moved)
│   ├── event_system.py         # AutonomousEvent (moved)
│   ├── event_queue.py          # EventQueue (moved)
│   ├── event_processor.py      # EventProcessor (moved; uses noesium.core.msgbus.BaseWatchdog)
│   ├── event_sources.py        # TimerEventSource, FileSystemEventSource, WebhookEventSource (moved)
│   └── trigger.py              # Trigger, TriggerRule (moved)
│
├── prompts/                    # Prompt manager and templates
│   └── ...
│
└── legacy/                     # Deprecated; migrate or remove over time
    └── gem_parser.py
```

### 4.2 Module Responsibilities (Spec-Aligned)

| Layer | Module | Responsibility | Spec |
|-------|--------|----------------|------|
| Application | `agent.py` | NoeAgent: lifecycle, mode (Ask/Agent), graph build, invoke; no orchestration above graph | RFC-1009 §5.3.4 |
| Application | `config.py` | NoeConfig, NoeMode, tool/subagent config; single place for app config | RFC-1009 §7.2 |
| Application | `cli_adapter.py`, `tui.py`, `commands.py` | CLI, TUI, inline commands | RFC-1009 §5.3.4 |
| Kernel | `kernel/core.py` | AgentKernel: step(goal, context) → Decision for Cognitive Loop | RFC-1005 §8 |
| Graph | `graph/builder.py` | Build Ask/Agent StateGraphs; single place for graph topology | RFC-0001 §5.2, RFC-2002 |
| Graph | `graph/nodes.py` | All node logic: plan, execute_step, tool, subagent, reflect, finalize, recall, generate_answer, revise_plan | RFC-2002 nodes as transformers |
| Graph | `graph/routing.py` | Conditional edges after execute/reflect | RFC-2002 |
| Capabilities | `capabilities/tools.py` | Tool setup, registry, MCP; tool descriptions | RFC-1004, RFC-1201 |
| Capabilities | `capabilities/subagents.py` | External + builtin subagent setup, SubagentManager registration | RFC-1005 §9, RFC-2004 |
| Autonomous | `autonomous/cognitive_loop.py` | Loop: next_goal → project → kernel.step → execute → memory update | RFC-1005 §7 |
| Autonomous | `autonomous/runner.py` | Entry point for autonomous mode | RFC-1005 |
| Shared | `state.py`, `schemas.py`, `planner.py` | State shapes, action schemas, planning (goal → plan) | RFC-2002, RFC-2004 |

### 4.3 Dependency Rules

- **noeagent** may import: `noesium.core`, `noesium.toolkits`, `noesium.subagents`. No other app packages.
- **Within noeagent**:  
  - `agent.py` may import kernel, graph, capabilities, config, state, schemas, planner, commands, etc.  
  - `graph/builder.py` and `graph/routing.py` import from `graph/nodes.py` only (no import of `agent` to avoid cycles).  
  - `kernel/core.py` imports `NoeAgent` (TYPE_CHECKING or late import acceptable).  
  - `autonomous/cognitive_loop.py` imports GoalEngine, memory, AgentKernel, CapabilityRegistry from noesium/core and noeagent.kernel.

### 4.4 Critical Fix: Add `graph/nodes.py`

The proposed structure **requires** adding the missing `graph/nodes.py` and consolidating there:

- **Ask graph**: `recall_memory_node`, `generate_answer_node`
- **Agent graph**: `plan_node`, `execute_step_node`, `tool_node`, `subagent_node`, `reflect_node`, `revise_plan_node`, `finalize_node`
- Helpers used by nodes or agent: e.g. `_build_tool_descriptions`, `_persist_plan_to_memory` (can live in `nodes.py` or a small `graph/helpers.py` used only by graph/agent).

After adding `graph/nodes.py`:

- `graph/__init__.py` should re-export from `.nodes` and `.builder`, `.routing` as it does today.
- `graph/builder.py` should keep using `from . import nodes` (or `from .nodes import ...`).
- `agent.py` should import helpers from `noeagent.graph.nodes` (or `noeagent.graph`) instead of `noeagent.nodes`.
- Tests should use `from noeagent.graph.nodes import ...` (or `from noeagent.graph import ...`) instead of `noeagent.nodes`.

This restores a single, spec-aligned place for all LangGraph node logic (RFC-2002 “nodes as transformers”).

---

## 5. Optional Consolidations

- **Goal Engine and Event System**: Moved from `noesium.core.autonomous` into `noeagent.autonomous`. Noeagent owns Goal, GoalEngine, CognitiveLoop, EventProcessor, EventQueue, triggers, and event sources; noesium.core no longer contains an autonomous package.
- **Memory**: Use noesium.core memory (ProviderMemoryManager, tiers) from agent and nodes; noeagent does not define a separate memory layer.
- **Legacy**: Keep `legacy/gem_parser` behind a clear boundary; migrate or remove when no longer needed.
- **Remove empty dirs**: If `session/` or `ui/` exist with only `__init__.py` and no logic, remove them (per plan-2026-03-08-001).
- **Remove duplicate subagent code**: Ensure a single implementation (e.g. `capabilities/subagents.py`); delete any unused root-level subagent module if present.

---

## 6. Move noesium.core.autonomous to noeagent (Done)

The entire `noesium/core/autonomous` package has been moved into `noeagent/autonomous` so that:

- **Goal Engine**, **Event System**, **Trigger rules**, and **Decision schema** live in the application layer (noeagent) rather than in the framework core.
- Noesium core remains free of application-specific autonomous loop semantics; noeagent depends on noesium for event envelope, memory provider, and msgbus only.

**Moved modules:** `models.py`, `goal_engine.py`, `decision_schema.py`, `events.py`, `event_system.py`, `event_queue.py`, `event_processor.py`, `event_sources.py`, `trigger.py`.

**Noesium changes:** Remove `noesium/core/autonomous/` directory and remove `"autonomous"` from `noesium/core/__init__.py` `__all__`.

**Noeagent changes:** Add the above modules under `noeagent/autonomous/`, merge `autonomous/__init__.py` to re-export Goal, GoalEngine, events, EventProcessor, etc., and update `cognitive_loop.py`, `runner.py`, and `kernel/core.py` to import from `noeagent.autonomous` (local) instead of `noesium.core.autonomous`.

---

## 7. Files to Create or Change (Summary)

| Action | Path |
|--------|------|
| **Create** | `noeagent/src/noeagent/graph/nodes.py` — implement or move all node functions and node-scoped helpers |
| **Update** | `noeagent/src/noeagent/agent.py` — switch `from .nodes import _build_tool_descriptions` to `from .graph.nodes import _build_tool_descriptions` (or equivalent) |
| **Update** | Tests — replace `noeagent.nodes` imports with `noeagent.graph.nodes` or `noeagent.graph` |
| **Verify** | `capabilities/subagents.py` exists and is the single place for external/builtin subagent setup |
| **Optional** | Remove empty `session/`, `ui/` if present; remove unused `subagent_runtimes.py` if duplication exists |

---

## 7. Verification

- All imports resolve; no reference to missing `noeagent.nodes`.
- `from noeagent.graph import build_ask_graph, build_agent_graph, ...` and node names work.
- NoeAgent Ask and Agent modes run; autonomous path uses AgentKernel + CognitiveLoop.
- Layering: noeagent does not import from other application packages; noesium does not import noeagent (RFC-1009).
- Lint and tests pass after adding `graph/nodes.py` and updating imports.

---

## 8. Relationship to Other Docs

- **plan-2026-03-08-001.md**: Fixes kernel export and empty dirs; this proposal adds the **graph/nodes** fix and a full spec-aligned layout.
- **RFC-1005**: Five-component architecture is reflected in `kernel/`, `graph/`, `capabilities/`, `autonomous/`, and memory via noesium.
- **RFC-1009**: noeagent remains the only Application Layer package depending on noesium.
