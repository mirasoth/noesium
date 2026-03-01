# Gap Analysis: RFCs / Implementation Guides vs Current Codebase

> Analysis of gaps between the Noesium specification system (RFC-0001 through RFC-1002) and the current implementation.
>
> **Date**: 2026-03-01
> **Scope**: `noesium/core/`, `noesium/agents/`, `noesium/toolkits/`

---

## 1. Executive Summary

The Noesium codebase provides a functional agent framework with LangGraph integration, 17+ toolkits, LLM abstraction, memory system, and three working agents. However, significant gaps exist between the current implementation and the event-sourced, deterministic kernel architecture specified in the RFCs. The gaps are categorized into four tiers: **Critical** (core architectural gaps), **Major** (significant missing modules), **Moderate** (partial implementations), and **Minor** (cosmetic or organizational).

### Gap Score by Module

| Module | RFC Coverage | Implementation Status | Gap Severity |
|--------|-------------|----------------------|--------------|
| Event System | RFC-0001, RFC-0002, RFC-1001 | **Missing** | Critical |
| Kernel Executor | RFC-0003, RFC-1001 | **Missing** | Critical |
| Projection Layer | RFC-0004, RFC-1001 | **Missing** | Critical |
| Capability Registry | RFC-0005, RFC-1001 | **Missing** | Major |
| Memory Hierarchy | RFC-0004, RFC-1001 | **Partial** | Moderate |
| Agent Base Classes | RFC-1001, RFC-1002 | **Exists, needs extension** | Moderate |
| Event Bus (msgbus) | RFC-0001, RFC-1001 | **Partial** (bubus only) | Major |
| Tool System (Toolify) | RFC-1001 | **Exists** | Minor |
| LLM Integration | RFC-1001 | **Exists** | Minor |
| Tracing / Observability | RFC-1001 | **Exists** | Minor |
| Agent Implementations | RFC-1002 | **Exists** | Moderate |

---

## 2. Critical Gaps

### 2.1 Event System (`core/event/`) — NOT IMPLEMENTED

**RFC Reference**: RFC-0001 §5, RFC-0002 (entire), RFC-1001 §6

**What's Missing**:
- `EventEnvelope` Pydantic model (RFC-0002 canonical structure)
- `AgentRef`, `TraceContext`, `SignatureBlock` models
- `DomainEvent` abstract base with typed event classes
- `EventStore` interface and implementations (`InMemoryEventStore`, `FileEventStore`)
- Event type registry
- JSON canonicalization (RFC 8785)

**Current State**: The codebase uses `bubus.BaseEvent` and `bubus.EventBus` in `core/msgbus/` and `agents/browser_use/`. These are in-process events without the RFC-0002 envelope structure (no spec_version, trace context, causation/correlation IDs, signature blocks).

**Impact**: Without event envelopes, no replayability, no distributed tracing, no audit trail.

**Priority**: **P0** — Foundation for all other new modules.

---

### 2.2 Kernel Executor (`core/kernel/`) — NOT IMPLEMENTED

**RFC Reference**: RFC-0003 (entire), RFC-1001 §7

**What's Missing**:
- `KernelExecutor` wrapping LangGraph with event emission
- `NodeResult` model (state_delta + events)
- `CheckpointManager` aligning checkpoints with event boundaries
- `@kernel_node` decorator for determinism annotation
- Topological scheduler

**Current State**: Agents compile LangGraph `StateGraph` directly and invoke via `graph.invoke()` / `graph.ainvoke()`. No event emission on node entry/exit. No determinism tracking. Checkpointing exists only in AskuraAgent via `InMemorySaver`.

**Impact**: No event-mediated execution, no node-level observability beyond logging, no deterministic replay capability.

**Priority**: **P0** — Required to bridge current graph execution with event-sourced model.

---

### 2.3 Projection Layer (`core/projection/`) — NOT IMPLEMENTED

**RFC Reference**: RFC-0004 (entire), RFC-1001 §8

**What's Missing**:
- `BaseProjection[TState]` generic abstract class
- `ProjectionEngine` with caching and incremental update
- `ExecutionProjection` for workflow state
- `CognitiveProjection` for conversation/reasoning traces
- `SemanticProjection` wrapping vector store indexing

**Current State**: State is mutable and stored directly. No projection-based state derivation. No event-sourced state reconstruction.

**Impact**: State is not replayable, not auditable, and not recoverable from event logs.

**Priority**: **P1** — Depends on Event System being implemented first.

---

## 3. Major Gaps

### 3.1 Capability Registry (`core/capability/`) — NOT IMPLEMENTED

**RFC Reference**: RFC-0005 (entire), RFC-1001 §10

**What's Missing**:
- `Capability` model with schemas, determinism/side-effect/latency classifications
- `CapabilityRegistry` (projection-based)
- `DiscoveryService` for capability queries
- `DeterministicResolver` for capability selection
- Capability lifecycle events (registered, deprecated, invoked, completed)

**Current State**: No capability declaration or discovery. Agents are instantiated directly. Inter-agent delegation does not exist — each agent operates independently.

**Impact**: No multi-agent collaboration, no capability-based routing, no typed contracts between agents.

**Priority**: **P2** — Depends on Event System and Projection Layer.

---

### 3.2 Event Bus Bridge (`core/msgbus/bridge.py`) — NOT IMPLEMENTED

**RFC Reference**: RFC-1001 §6.4

**What's Missing**:
- `EnvelopeBridge` adapting bubus `BaseEvent` ↔ `EventEnvelope`
- `EnvelopeEvent` bubus wrapper
- Bidirectional publish/subscribe with envelope typing

**Current State**: `core/msgbus/` provides `BaseWatchdog` and `EventProcessor` protocol, but no bridge to RFC-0002 envelopes. bubus events are plain objects without canonical structure.

**Impact**: Cannot publish RFC-0002 compliant events to the existing bus.

**Priority**: **P1** — Required to connect event system with existing bus infrastructure.

---

## 4. Moderate Gaps

### 4.1 Memory Hierarchy — PARTIALLY IMPLEMENTED

**RFC Reference**: RFC-0004 §5, RFC-1001 §9

| Layer | RFC | Current State | Gap |
|-------|-----|---------------|-----|
| Ephemeral Memory | RFC-0004 §5.1 | Not separate class; in-memory state in agents | Need `EphemeralMemory` class |
| Durable Memory | RFC-0004 §5.2 | `BaseMemoryStore` + Memu `MemoryAgent` (direct mutation, not event-sourced) | Need event-sourced `DurableMemory` |
| Semantic Memory | RFC-0004 §5.3 | `BaseVectorStore` + Memu embeddings | Exists but not tied to event-sourced durable layer |
| Memory Manager | RFC-1001 §9.4 | `BaseMemoryManager` ABC (no unified composing class) | Need `MemoryManager` composing all three layers |

**Summary**: Memory infrastructure exists but is not event-sourced and lacks the formal three-layer hierarchy.

---

### 4.2 Agent Base Classes — NEEDS EXTENSION

**RFC Reference**: RFC-1001 §11, RFC-1002 §5

| Issue | Detail |
|-------|--------|
| All base classes in one file | `base.py` contains `BaseAgent`, `BaseGraphicAgent`, `BaseConversationAgent`, `BaseResearcher` — RFC-1001 recommends splitting into separate files |
| No event store in BaseAgent | RFC-1001 adds `event_store`, `projection_engine`, `memory_manager` to BaseAgent |
| No kernel executor in BaseGraphicAgent | RFC-1001 adds `KernelExecutor` wrapping |
| No capability declaration | RFC-1001 adds `declare_capability()` to BaseGraphicAgent |
| No execution mode | RFC-1001 adds `ExecutionMode` configuration |

**Summary**: Base classes work well for current agents but need extension for new core infrastructure. Refactoring is non-breaking.

---

### 4.3 Agent Implementation Patterns — INCONSISTENT

**RFC Reference**: RFC-1002 §6-8

| Pattern | RFC-1002 Spec | Current State |
|---------|---------------|---------------|
| State model | TypedDict or Pydantic, consistent per archetype | AskuraAgent uses Pydantic; SearchAgent/DeepResearch use TypedDict ✅ |
| Node signatures | `async def _name_node(self, state, config) -> dict` | Mixed sync/async, some return full state, some return dict |
| Node naming | `_<name>_node` | Mostly consistent ✅ |
| Error handling | Structured error responses for conversations | AskuraAgent has it ✅; SearchAgent uses emoji strings ⚠️ |
| Graph construction | Canonical 6-step pattern | Similar but not standardized |
| Event emission from nodes | `_pending_events` field | Not implemented |

---

## 5. Minor Gaps

### 5.1 Tool System (Toolify) — WELL-ALIGNED

**Current State**: 17+ toolkits registered via `@register_toolkit`, auto-discovery, LangChain/MCP conversion. RFC-1001 §12 adds event-mediated tool execution for strict mode, which is additive.

**Gap**: No `ToolInvocationRequested`/`ToolInvocationCompleted` events for strict mode.

---

### 5.2 LLM Integration — WELL-ALIGNED

**Current State**: `BaseLLMClient` with 5 providers, structured completion via instructor. RFC-1001 doesn't change this.

**Gap**: None significant.

---

### 5.3 Tracing / Observability — WELL-ALIGNED

**Current State**: `TokenUsageTracker`, `NodeLoggingCallback`, `TokenUsageCallback`, Opik integration. RFC-1001 §15 adds event-based metrics counters.

**Gap**: No event-based metrics, but existing tracing works well.

---

### 5.4 Goal Management (Goalith) — PARTIALLY IMPLEMENTED, NOT IN RFCs

**Current State**: `GoalithService` (stub), `GoalDecomposer`, `GoalGraph`, `ConflictResolver`, `Replanner`. Not referenced in current RFCs.

**Recommendation**: Consider RFC-2xxx for goal management enhancement specification.

---

### 5.5 Model Routing — EXISTS, NOT IN RFCs

**Current State**: `ModelRouter` with `SelfAssessmentStrategy`, `DynamicComplexityStrategy`. Not referenced in current RFCs.

**Recommendation**: Consider RFC-2xxx for routing specification.

---

## 6. Dependency Graph for Gap Resolution

```
Phase 1 (P0):  core/event/          ← Foundation
                    │
Phase 2 (P0):  core/kernel/         ← Wraps LangGraph with events
                core/msgbus/bridge   ← Connects event envelope to bubus
                    │
Phase 3 (P1):  core/projection/     ← State derivation from events
                core/memory/{ephemeral,durable,semantic,manager}
                    │
Phase 4 (P2):  core/capability/     ← Inter-agent discovery
                core/agent/ extensions (event_store, kernel, capabilities)
```

---

## 7. Recommended Implementation Order

### Phase 1: Event Infrastructure (estimated: 3-5 days)

1. Create `core/event/envelope.py` — `EventEnvelope`, `AgentRef`, `TraceContext`
2. Create `core/event/types.py` — `DomainEvent`, standard event classes
3. Create `core/event/store.py` — `EventStore` ABC, `InMemoryEventStore`
4. Create `core/event/codec.py` — Serialization utilities
5. Create `core/msgbus/bridge.py` — `EnvelopeBridge`
6. Tests for all above

### Phase 2: Kernel Executor (estimated: 3-5 days)

1. Create `core/kernel/executor.py` — `KernelExecutor`
2. Create `core/kernel/decorators.py` — `@kernel_node`
3. Create `core/kernel/checkpoint.py` — `CheckpointManager`
4. Integrate with `BaseGraphicAgent` (opt-in via `execution_mode`)
5. Tests

### Phase 3: Projection and Memory (estimated: 5-7 days)

1. Create `core/projection/base.py` — `BaseProjection`, `ProjectionEngine`
2. Create `core/projection/execution.py` — `ExecutionProjection`
3. Create `core/projection/cognitive.py` — `CognitiveProjection`
4. Create `core/memory/ephemeral.py`, `durable.py`, `semantic.py`, `manager.py`
5. Integrate with `BaseAgent` (opt-in via `enable_projections`)
6. Tests

### Phase 4: Capability Registry (estimated: 3-5 days)

1. Create `core/capability/models.py` — `Capability`, enums
2. Create `core/capability/registry.py` — `CapabilityRegistry`
3. Create `core/capability/discovery.py` — `DiscoveryService`
4. Create `core/capability/resolution.py` — `DeterministicResolver`
5. Add `declare_capability()` to `BaseGraphicAgent`
6. Tests

### Phase 5: Agent Alignment (estimated: 2-3 days)

1. Split `core/agent/base.py` into separate files
2. Standardize node signatures across agents
3. Add structured error responses to SearchAgent
4. Standardize graph construction patterns
5. Update agent demos

---

## 8. What Works Well (No Changes Needed)

- LangGraph integration pattern (StateGraph → compile → invoke)
- Toolkit system (Toolify) with auto-discovery and 17+ toolkits
- LLM client abstraction with 5 providers
- AskuraAgent's HITL pattern with InMemorySaver
- DeepResearchAgent's Send/fan-out pattern
- Token usage tracking
- Memu memory subsystem (can coexist with new layers)
- Browser_use agent with event bus integration (bubus)

---

## 9. Risks and Considerations

1. **Backward Compatibility**: All new modules MUST be additive and opt-in. Existing agents MUST not break.
2. **Performance**: Event emission on every node adds overhead. Pragmatic mode should be the default.
3. **Complexity**: Full event-sourced architecture is significant. Incremental adoption via `ExecutionMode` is essential.
4. **Testing**: Each phase needs comprehensive tests before moving to the next.
5. **Dependencies**: `uuid7` package needed for UUIDv7 generation. Verify `bubus` API supports the bridge pattern.
