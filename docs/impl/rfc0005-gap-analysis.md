# RFC-0005 Implementation Gap Analysis Report

**Date**: 2026-03-03
**RFC**: RFC-0005 - Capability Registry and Discovery Protocol
**Analysis Team**: 8 specialized agents working in parallel

---

## Executive Summary

This report analyzes the implementation gaps between **RFC-0005: Capability Registry and Discovery Protocol** and the current Noesium codebase.

### Overall Assessment

**Implementation Maturity**: 50-60% Complete

- ✅ **Fully Implemented**: Registry as Projection (Section 4.4)
- ⚠️ **Partially Implemented**: Event Schema, Discovery Protocol, Subagent Architecture, Subagent Lifecycle, Invocation Flow
- ❌ **Not Implemented**: Capability Type Taxonomy, Health & Liveness Model

### Critical Blocking Gaps

1. **Missing `CapabilityType` Enum** (Section 4.2) - BLOCKS full RFC compliance
2. **Missing Health & Liveness Model** (Section 8) - BLOCKS production readiness
3. **Missing Event-Mediated Invocation** (Section 7) - ARCHITECTURAL mismatch

---

## Detailed Analysis by Section

### 1. Capability Definition and Type Taxonomy (Section 4.1-4.3)

**Status**: ⚠️ 70% Complete

#### ✅ Implemented

- `Capability` model with core fields: id, version, input_schema, output_schema, determinism, side_effects, latency, tags, roles, scopes
- `CapabilityRegistered`, `CapabilityInvoked`, `CapabilityCompleted` events
- `CapabilityRegistry` with register() and deprecate() methods
- `CapabilityProjection` for event-sourced state derivation
- Enum types: DeterminismClass, SideEffectClass, LatencyClass

#### ❌ Critical Missing Components

| Component | RFC Requirement | Status | Impact |
|-----------|----------------|--------|--------|
| `CapabilityType` enum | InProcessTool, RemoteTool, Subagent, ExternalCliSubagent | NOT IMPLEMENTED | **CRITICAL** - Blocks tool vs subagent distinction |
| `capability_type` field | Required in Capability model | NOT IMPLEMENTED | **CRITICAL** - Cannot classify capabilities |
| `CapabilityUpdated` event | Section 4.3 | NOT IMPLEMENTED | MEDIUM - Missing lifecycle event |
| Agent capability declaration | Self-declaration pattern | PARTIAL | MEDIUM - No agent-level API |

**Files Analyzed**:
- `noesium/core/capability/models.py:30-47` - Capability model
- `noesium/core/capability/registry.py` - Registry implementation
- `noesium/core/event/types.py:89-114` - Event definitions

**Recommendation**:
```python
# Add to models.py
class CapabilityType(str, Enum):
    IN_PROCESS_TOOL = "InProcessTool"
    REMOTE_TOOL = "RemoteTool"
    SUBAGENT = "Subagent"
    EXTERNAL_CLI_SUBAGENT = "ExternalCliSubagent"

class Capability(BaseModel):
    # ... existing fields ...
    capability_type: CapabilityType  # ADD THIS
```

---

### 2. Registry as Projection (Section 4.4)

**Status**: ✅ 100% Complete - FULLY ALIGNED

#### Implementation Verification

✅ Registry is NOT a database table
✅ Projection function: `RegistryState = fold(P_registry, ∅, EventStream)`
✅ Pure function: `P_registry : (State, Event) → State`
✅ Deterministic and replayable
✅ No IO in projection
✅ Aligned with RFC-0003 and RFC-0004

**Files Analyzed**:
- `noesium/core/capability/registry.py` - CapabilityProjection and CapabilityRegistry
- `noesium/core/projection/base.py` - BaseProjection and ProjectionEngine
- `noesium/core/event/store.py` - EventStore (append-only log)

**Evidence**:
```python
# registry.py:15-43
class CapabilityProjection(BaseProjection[dict[str, Any]]):
    def initial_state(self) -> dict[str, Any]:
        return {"capabilities": {}, "deprecated": set()}

    def apply(self, state: dict[str, Any], event: EventEnvelope) -> dict[str, Any]:
        # Pure transformation based on event type
        if et == "capability.registered":
            state["capabilities"][key] = {...}
        elif et == "capability.deprecated":
            state["deprecated"].add(key)
        return state
```

**Note**: Legacy `noesium/core/toolify/registry.py` exists but is not part of RFC-compliant capability system.

---

### 3. Event Schema (Section 5)

**Status**: ⚠️ 60% Complete

#### ✅ Implemented

- Event Envelope structure (RFC-0002 compliant)
- UUIDv7 for event IDs
- TraceContext with parent_span_id and depth
- `CapabilityRegistered` event type: "capability.registered"
- `CapabilityInvoked` event type: "capability.invoked"
- Event emission infrastructure in CapabilityRegistry

#### ⚠️ Partial Implementation

| Event | RFC Section | Status | Gap |
|-------|-------------|--------|-----|
| CapabilityRegistered | 5.1 | PARTIAL | Missing explicit field definitions in event class |
| CapabilityDeprecated | 5.2 | PARTIAL | No event class, only raw EventEnvelope emission |
| CapabilityInvoked | 5.3 | COMPLETE | All fields present |

#### ❌ Missing

- `CapabilityUpdated` event
- Explicit field definitions in event classes (input_schema, output_schema, metadata)
- `capability_type` field in CapabilityRegistered payload

**Files Analyzed**:
- `noesium/core/event/types.py:89-114` - Event definitions
- `noesium/core/event/envelope.py` - Event envelope structure
- `noesium/core/capability/registry.py:64-87` - Event emission

**Recommendation**:
```python
# Add explicit event classes
class CapabilityRegistered(DomainEvent):
    capability_id: str
    version: str
    agent_id: str
    capability_type: CapabilityType  # ADD
    input_schema: dict              # ADD
    output_schema: dict             # ADD
    metadata: dict = {}             # ADD

class CapabilityDeprecated(DomainEvent):  # ADD CLASS
    capability_id: str
    version: str
    reason: str
```

---

### 4. Discovery Protocol (Section 6)

**Status**: ⚠️ 75% Complete

#### ✅ Implemented

- `find(capability_id, version_range)` query
- `find_by_tag(tag)` query
- `find_by_determinism(cls)` query
- Deterministic resolution by registration order
- Deprecated capability filtering
- Version filtering (prefix-based)

#### ❌ Missing

| Component | RFC Requirement | Status | Priority |
|-----------|----------------|--------|----------|
| `find_by_capability_type()` | Section 6.1 | NOT IMPLEMENTED | HIGH |
| Health status filtering | Section 6.2 | NOT IMPLEMENTED | HIGH |
| Proper semver compatibility | Section 12 | NOT IMPLEMENTED | MEDIUM |

#### Implementation Gaps

**Version Compatibility**:
- Current: Simple prefix matching (`str.startswith()`)
- RFC Required: Semver rules (major mismatch → incompatible, minor upgrade → compatible, patch upgrade → safe)
- Issue: Version "2" would incorrectly match "20.0.0"

**Health Filtering**:
- RFC-0005 Section 8 requires health status consideration
- No health projection or filtering exists

**Files Analyzed**:
- `noesium/core/capability/discovery.py` - DiscoveryService
- `noesium/core/capability/resolution.py` - DeterministicResolver

**Recommendation**:
```python
# Add to DiscoveryService
async def find_by_capability_type(self, capability_type: CapabilityType) -> list[Capability]:
    state = await self._engine.get_state("capability")
    return [
        cap for cap in state["capabilities"].values()
        if cap.get("capability_type") == capability_type and not cap.get("deprecated")
    ]
```

---

### 5. Invocation Flow (Section 7)

**Status**: ⚠️ 40% Complete - ARCHITECTURAL MISMATCH

#### Current Architecture vs RFC-0005

**Current Flow**:
```
NoeAgent → execute_step_node → tool_node → ToolExecutor.run(tool)
                                    ↓
                              tool.invoked/completed events
```

**RFC-0005 Required Flow**:
```
Agent → emit(capability.requested) → Kernel → resolve(capability_id)
                                                    ↓
                                          emit(capability.invoked)
                                                    ↓
                                          ToolExecutor.run(tool)
                                                    ↓
                                          emit(capability.completed)
```

#### ✅ What Works

**Tool Invocation**:
- Direct tool execution via `ToolExecutor.run()`
- Tool-level events: `tool.invoked`, `tool.completed`, `tool.failed`, `tool.timeout`
- Arg validation and coercion
- Permission checks
- Timeout handling

**Subagent Invocation**:
- In-process subagents: Direct `NoeAgent()` child instantiation
- External CLI subagents: Persistent daemon spawning via `ExternalCliAdapter`
- Lifecycle management: CREATED → RUNNING → BUSY → IDLE → TERMINATED
- stdin/stdout JSON streaming
- Health checks and restart policies

#### ❌ Critical Missing Components

| Component | RFC Requirement | Status | Impact |
|-----------|----------------|--------|--------|
| `capability.requested` event | Section 7.1-7.2 | NOT IMPLEMENTED | CRITICAL |
| Kernel capability resolution | Before invocation | NOT INTEGRATED | CRITICAL |
| `capability.invoked` event | Kernel emits | DEFINED BUT UNUSED | CRITICAL |
| `capability.completed` event | Result return | DEFINED BUT UNUSED | CRITICAL |
| Event correlation | correlation_id tracking | NOT IMPLEMENTED | HIGH |

**Files Analyzed**:
- `noesium/core/toolify/executor.py` - Tool execution
- `noesium/noe/nodes.py:257-317` - tool_node
- `noesium/noe/nodes.py:320-380` - subagent_node
- `noesium/noe/agent.py:667-689` - Subagent spawning
- `noesium/noe/cli_adapter.py` - External CLI adapter

**Gap Analysis**:

The capability system exists but is **not connected** to actual tool/subagent invocation. Tools execute directly without capability resolution. The `CapabilityRegistry`, `DiscoveryService`, and `DeterministicResolver` work correctly for registration and discovery, but are bypassed during actual invocation.

**Recommendation**:
1. Add `capability.requested` event emission before tool/subagent calls
2. Integrate `DeterministicResolver` into execution path
3. Emit `capability.invoked` and `capability.completed` events
4. Add correlation_id tracking across capability lifecycle

---

### 6. Health & Liveness Model (Section 8)

**Status**: ❌ 0% Complete - NOT IMPLEMENTED

#### RFC Requirements vs Reality

| Component | RFC Section | Status |
|-----------|-------------|--------|
| `agent.heartbeat` event | 8.0 | NOT IMPLEMENTED |
| `agent.unavailable` event | 8.0 | NOT IMPLEMENTED |
| `agent.recovered` event | 8.0 | NOT IMPLEMENTED |
| HealthState projection | 8.0 | NOT IMPLEMENTED |
| Resolution excludes unhealthy agents | 8.0 | NOT IMPLEMENTED |
| Subagent liveness monitoring | 8.1 | PARTIAL |

#### Partial Implementation

**CLI Subagent Health Check**:
- `ExternalCliAdapter.health_check()` method exists (cli_adapter.py:153)
- Checks if process is alive via `proc.returncode is None`
- But: No heartbeat emission, no projection integration, no automatic health transitions

**Files Analyzed**:
- `noesium/core/event/types.py` - No health events defined
- `noesium/core/projection/` - No health projection
- `noesium/noe/cli_adapter.py:153-158` - Basic health check

**Impact**: CRITICAL for production readiness

Without health monitoring:
- No automatic failover
- No service discovery health awareness
- Unhealthy agents continue receiving requests
- No liveness validation for long-running subagents

**Recommendation**:

```python
# 1. Add event types (core/event/types.py)
class AgentHeartbeat(DomainEvent):
    agent_id: str
    timestamp: datetime

class AgentUnavailable(DomainEvent):
    agent_id: str
    reason: str

class AgentRecovered(DomainEvent):
    agent_id: str

# 2. Add health projection (core/projection/health.py)
class HealthProjection(BaseProjection[dict[str, HealthState]]):
    def apply(self, state, event):
        if event.event_type == "agent.heartbeat":
            state[event.payload["agent_id"]].last_heartbeat = event.timestamp
        elif event.event_type == "agent.unavailable":
            state[event.payload["agent_id"]].status = "unhealthy"
        # ...

# 3. Integrate with DiscoveryService
async def find(self, capability_id: str, version_range: str | None = None):
    capabilities = await self._query_capabilities(capability_id, version_range)
    health_state = await self._engine.get_state("health")
    return [cap for cap in capabilities if health_state.get(cap.agent_id, {}).get("status") != "unhealthy"]
```

---

### 7. Persistent Subagent Architecture (Section 10)

**Status**: ⚠️ 60% Complete

#### ✅ Implemented

**SubagentAdapter Interface** (Partial):
- `spawn(name, initial_message)` → str
- `health_check(name)` → bool
- `restart(name)` → str
- `terminate(name)` → str
- `SubagentHandle` with state management

**Lifecycle Management**:
- State machine: CREATED → RUNNING → BUSY → IDLE → TERMINATED
- Session-scoped state persistence
- Daemon process management
- Cleanup via `terminate_all()`

**Communication**:
- stdin/stdout JSON streaming
- Line-delimited JSON format
- Timeout handling

#### ❌ Missing Components

| Component | RFC Requirement | Status | Priority |
|-----------|----------------|--------|----------|
| `send(message) → RequestID` | Async send | Returns response directly | MEDIUM |
| `receive()` method | Async receive | Not implemented (sync) | MEDIUM |
| Request-response correlation | request_id tracking | Not implemented | MEDIUM |
| Structured envelope | request_id, task, payload, context | Simple {"message": ...} | MEDIUM |
| Capability registration | Via CapabilityRegistry | Config-only | HIGH |
| `stateful: true` declaration | Required metadata | Not declared | MEDIUM |
| Concurrency model | Serial, limited-parallel | Not defined | MEDIUM |
| Resource cost hints | Memory, CPU class | Not defined | LOW |

**Files Analyzed**:
- `noesium/noe/cli_adapter.py` - ExternalCliAdapter
- `noesium/noe/config.py:20-30` - CliSubagentConfig
- `noesium/noe/agent.py:667-689` - Subagent management

**Current Message Format**:
```json
{"message": "user message"}
```

**RFC Required Envelope**:
```json
{
  "request_id": "uuid",
  "task": "description",
  "payload": "...",
  "context": {...}
}
```

**Gap**: No unified SubagentAdapter interface for both in-process and CLI subagents.

**Recommendation**:
1. Add structured communication envelope with request_id
2. Implement async request-response correlation
3. Integrate CLI subagents with CapabilityRegistry
4. Add missing metadata fields to CliSubagentConfig

---

### 8. Subagent Lifecycle Model (Section 11)

**Status**: ⚠️ 70% Complete

#### ✅ Implemented

**State Machine** (FULLY IMPLEMENTED):
- All 5 states: CREATED, RUNNING, BUSY, IDLE, TERMINATED
- All required transitions:
  - `CREATED → RUNNING`: `_spawn_with_config()`
  - `RUNNING → BUSY`: `_send_unlocked()`
  - `BUSY → IDLE`: After task completion
  - `IDLE → BUSY`: New task dispatch
  - `IDLE/BUSY → TERMINATED`: `_terminate_proc()`

**Failure Recovery**:
- `health_check()` implemented
- `restart()` implemented (terminate + re-spawn)
- Reuse active sessions

**Scheduling**:
- Timeout enforcement
- Depth limits (`subagent_max_depth: int = 2`)

#### ⚠️ Partial Implementation

| Component | RFC Requirement | Status | Gap |
|-----------|----------------|--------|-----|
| Task queuing | Queue if BUSY | NOT IMPLEMENTED | Uses asyncio.Lock, no queue |
| Concurrency caps | Per session/user | PARTIAL | Depth limit only, no parallel cap |
| Resource limits | Memory, CPU, time | PARTIAL | Timeout only, no memory/CPU limits |

#### ❌ Missing Components

| Component | RFC Requirement | Status |
|-----------|----------------|--------|
| Session context restoration | Best effort on restart | NOT IMPLEMENTED |
| Failure escalation | To orchestrator | NOT IMPLEMENTED |

**Files Analyzed**:
- `noesium/noe/cli_adapter.py` - ExternalCliAdapter
- `noesium/noe/agent.py:667-689` - Subagent management
- `noesium/noe/config.py:94-96` - Configuration

**Current Approach**:
- Uses `asyncio.Lock()` for mutual exclusion
- New requests wait for lock but aren't queued
- Restart loses all session state (no restoration)
- No retry limits or escalation logic

**Recommendation**:
1. Add task queue for BUSY subagents
2. Implement failure escalation with retry limits
3. Add concurrency caps for parallel CLI subagent execution
4. Implement session context snapshot/restore (best effort)

---

## Critical Gap Summary

### Blocking Gaps (Must Fix for RFC Compliance)

1. **Missing `CapabilityType` Enum** (Section 4.2)
   - **Impact**: Cannot distinguish tools from subagents
   - **Blocks**: Section 7 invocation patterns, Section 10 subagent architecture, Section 11 lifecycle
   - **Effort**: LOW - Add enum and field
   - **Priority**: P0

2. **Missing Health & Liveness Model** (Section 8)
   - **Impact**: No failover, unhealthy agents receive requests
   - **Blocks**: Production readiness, reliability
   - **Effort**: MEDIUM - Add events, projection, integration
   - **Priority**: P0

3. **Missing Event-Mediated Invocation** (Section 7)
   - **Impact**: Capability system disconnected from execution
   - **Blocks**: Full RFC compliance
   - **Effort**: HIGH - Architectural integration required
   - **Priority**: P1

### High Priority Gaps

4. **Missing Task Queuing for Subagents** (Section 11.3)
   - **Impact**: No proper handling of concurrent requests to BUSY subagents
   - **Effort**: MEDIUM
   - **Priority**: P1

5. **Missing Capability Type Filtering** (Section 6.1)
   - **Impact**: Cannot discover capabilities by type
   - **Effort**: LOW
   - **Priority**: P1

6. **Missing Health Status Filtering** (Section 6.2)
   - **Impact**: Unhealthy agents not excluded
   - **Effort**: MEDIUM (depends on Health Model)
   - **Priority**: P1

### Medium Priority Gaps

7. **Missing `CapabilityUpdated` Event** (Section 4.3)
   - **Impact**: Cannot track capability updates
   - **Effort**: LOW
   - **Priority**: P2

8. **Improper Semver Compatibility** (Section 12)
   - **Impact**: Incorrect version matching
   - **Effort**: LOW
   - **Priority**: P2

9. **Missing Subagent Communication Envelope** (Section 10.3)
   - **Impact**: No request correlation, limited context passing
   - **Effort**: MEDIUM
   - **Priority**: P2

10. **Missing Failure Escalation** (Section 11.2)
    - **Impact**: Silent failures
    - **Effort**: MEDIUM
    - **Priority**: P2

---

## Implementation Roadmap

### Phase 1: Foundation (P0 - Critical)

**Sprint 1: Capability Type Taxonomy** (2-3 days)
- Add `CapabilityType` enum to `core/capability/models.py`
- Add `capability_type` field to `Capability` model
- Update `CapabilityRegistered` event
- Add `find_by_capability_type()` to DiscoveryService
- Tests for capability type filtering

**Sprint 2: Health & Liveness** (5-7 days)
- Add health events: `AgentHeartbeat`, `AgentUnavailable`, `AgentRecovered`
- Implement `HealthProjection` class
- Add heartbeat emission to BaseAgent (background task)
- Integrate health filtering into DiscoveryService
- Add subagent liveness monitoring
- Integration tests for health-aware resolution

### Phase 2: Invocation Protocol (P1 - High)

**Sprint 3: Event-Mediated Invocation** (7-10 days)
- Add `capability.requested` event
- Integrate DeterministicResolver into execution path
- Emit `capability.invoked` and `capability.completed` events
- Add correlation_id tracking
- Update tool_node and subagent_node
- Integration tests for end-to-end capability flow

**Sprint 4: Subagent Enhancements** (5-7 days)
- Add task queuing for BUSY subagents
- Implement failure escalation with retry limits
- Add concurrency caps
- Improve communication envelope structure
- Tests for subagent queuing and escalation

### Phase 3: Polish (P2 - Medium)

**Sprint 5: Event and Version Improvements** (3-5 days)
- Add `CapabilityUpdated` event
- Implement proper semver compatibility checking
- Add missing event field definitions
- Tests for version compatibility

**Sprint 6: Subagent Metadata** (2-3 days)
- Add `stateful`, `concurrency`, `resource_cost` fields to CliSubagentConfig
- Integrate CLI subagent registration with CapabilityRegistry
- Documentation updates

---

## Compliance Matrix

| Section | Feature | Status | Completion |
|---------|---------|--------|-----------|
| 4.1 | Capability Definition | ⚠️ PARTIAL | 80% |
| 4.2 | Capability Type Taxonomy | ❌ MISSING | 0% |
| 4.3 | Agent Capability Set | ⚠️ PARTIAL | 70% |
| 4.4 | Registry as Projection | ✅ COMPLETE | 100% |
| 5.1 | CapabilityRegistered Event | ⚠️ PARTIAL | 60% |
| 5.2 | CapabilityDeprecated Event | ⚠️ PARTIAL | 50% |
| 5.3 | CapabilityInvoked Event | ✅ COMPLETE | 100% |
| 6.1 | Deterministic Query Model | ⚠️ PARTIAL | 75% |
| 6.2 | Resolution Algorithm | ⚠️ PARTIAL | 70% |
| 7.1 | Tool Invocation Flow | ⚠️ PARTIAL | 40% |
| 7.2 | Subagent Invocation Flow | ⚠️ PARTIAL | 40% |
| 8.0 | Health & Liveness Model | ❌ MISSING | 0% |
| 8.1 | Subagent Liveness | ⚠️ PARTIAL | 30% |
| 10.2 | SubagentAdapter Interface | ⚠️ PARTIAL | 60% |
| 10.3 | Communication Protocol | ⚠️ PARTIAL | 50% |
| 10.4 | Session Multiplexing | ⚠️ PARTIAL | 70% |
| 10.5 | Subagent Capability Registration | ❌ MISSING | 20% |
| 11.1 | Subagent States | ✅ COMPLETE | 100% |
| 11.2 | Failure Recovery | ⚠️ PARTIAL | 60% |
| 11.3 | Scheduling | ⚠️ PARTIAL | 60% |
| 12 | Version Negotiation | ⚠️ PARTIAL | 40% |

**Overall Compliance**: ~50-60%

---

## Strengths of Current Implementation

1. **Solid Event Sourcing Foundation**
   - Registry projection correctly implements fold pattern
   - Deterministic and replayable
   - Aligned with RFC-0003/RFC-0004

2. **Comprehensive Subagent Lifecycle**
   - Full state machine implementation
   - Proper process management
   - Health checks and restart mechanisms

3. **Working Tool Execution**
   - Robust ToolExecutor with validation, permissions, timeouts
   - Good event coverage at tool level
   - Production-ready for single-agent use

4. **Well-Structured Discovery**
   - Deterministic resolution
   - Multiple query methods
   - Clean separation of concerns

---

## Architectural Recommendations

### 1. Unify Tool and Capability Layers

**Current**: Tools and capabilities exist in separate worlds
- Tools execute directly
- Capabilities are registered but not used for invocation

**Recommended**: Connect capability resolution to tool execution
```python
# Before tool execution
capability = await resolver.resolve(tool_name)
emit(CapabilityInvoked(capability_id=capability.id))
result = await tool_executor.run(tool)
emit(CapabilityCompleted(result=result))
```

### 2. Establish Health as First-Class Concern

**Current**: No health monitoring infrastructure

**Recommended**:
- Add HealthProjection to core projection layer
- Require all agents to emit heartbeats
- Make health status mandatory for discovery results
- Add health dashboard/monitoring tools

### 3. Define Clear Tool vs Subagent Boundaries

**Current**: Implicit distinction based on execution path

**Recommended**: Use `CapabilityType` taxonomy consistently
- Tools: Stateless, atomic, no lifecycle management
- Subagents: Stateful, long-lived, lifecycle management required
- Different invocation patterns, monitoring, and recovery strategies

### 4. Strengthen Event Correlation

**Current**: Limited correlation across capability lifecycle

**Recommended**: Add correlation_id to all capability events
- Track request from `capability.requested` to `capability.completed`
- Enable distributed tracing
- Support debugging and auditing

---

## Conclusion

The Noesium codebase has a **solid foundation** for RFC-0005 compliance, particularly in:
- Event-sourced registry (Section 4.4) - FULLY IMPLEMENTED
- Subagent lifecycle management (Section 11.1) - FULLY IMPLEMENTED
- Discovery query model (Section 6.1) - 75% complete

However, **critical gaps** prevent full RFC compliance:

1. **Missing Capability Type Taxonomy** - The foundation for distinguishing tools from subagents
2. **Missing Health & Liveness Model** - Essential for production reliability
3. **Disconnected Capability System** - Capability registration exists but doesn't influence invocation

**Estimated effort for full compliance**: 3-4 sprints (30-40 developer-days)

**Recommended approach**: Implement Phase 1 (Foundation) immediately, then Phase 2 (Invocation Protocol) for architectural alignment, and Phase 3 (Polish) for completeness.

The codebase demonstrates good architectural patterns and would benefit significantly from closing these gaps to achieve the full vision of RFC-0005's capability-based, event-mediated multi-agent system.