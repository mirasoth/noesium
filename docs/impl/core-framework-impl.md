# Core Framework Implementation Architecture

> Implementation guide for the Noesium core framework in Python.
>
> **Module**: `noesium/core/`
> **Source**: Derived from [RFC-1001](../../specs/RFC-1001.md) (Core Framework Implementation Design)
> **Related RFCs**: [RFC-0001](../../specs/RFC-0001.md), [RFC-0002](../../specs/RFC-0002.md), [RFC-0003](../../specs/RFC-0003.md), [RFC-0004](../../specs/RFC-0004.md), [RFC-0005](../../specs/RFC-0005.md)

---

## 1. Overview

This guide describes how to implement the Noesium core framework modules defined in RFC-1001. The core framework provides the foundational infrastructure for all Noesium agents: event system, kernel executor, projection engine, capability registry, memory hierarchy, and base agent classes.

The implementation is incremental — existing agents MUST continue working throughout the migration. New modules are additive and gated by configuration flags.

**Language**: Python 3.11+
**Key dependencies**: Pydantic v2, LangGraph, bubus, uuid7

---

## 2. Architectural Position

```
┌─────────────────────────────────────────────────────────────┐
│                    Agents Layer                              │
│  (AskuraAgent, SearchAgent, DeepResearchAgent, ...)         │
└──────────────────────────┬──────────────────────────────────┘
                           │ uses
┌──────────────────────────▼──────────────────────────────────┐
│                   Core Framework                             │
│ ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐  │
│ │  event/   │ │ kernel/  │ │ projection/│ │ capability/  │  │
│ │ envelope  │ │ executor │ │ engine     │ │ registry     │  │
│ │ store     │ │ checkpoint│ │ exec/cog/  │ │ discovery    │  │
│ │ types     │ │ scheduler│ │ semantic   │ │ resolution   │  │
│ └─────┬─────┘ └─────┬────┘ └─────┬──────┘ └──────┬───────┘  │
│       │             │            │               │           │
│ ┌─────▼─────────────▼────────────▼───────────────▼─────────┐ │
│ │              Shared Infrastructure                        │ │
│ │  agent/base  memory/  llm/  msgbus/  toolify/  tracing/  │ │
│ └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**Dependency flow**: event/ ← kernel/ ← projection/ ← capability/

No circular dependencies between new modules. Each new module depends only on modules below it in the stack.

---

## 3. Module Structure

### 3.1 New Module: `core/event/`

```
noesium/core/event/
├── __init__.py          # Public exports: EventEnvelope, DomainEvent, EventStore, etc.
├── envelope.py          # EventEnvelope, AgentRef, TraceContext, SignatureBlock
├── types.py             # DomainEvent ABC, standard event classes
├── store.py             # EventStore ABC, InMemoryEventStore, FileEventStore
└── codec.py             # JSON serialization, canonicalization (RFC 8785)
```

### 3.2 New Module: `core/kernel/`

```
noesium/core/kernel/
├── __init__.py          # Public exports: KernelExecutor, NodeResult
├── executor.py          # KernelExecutor wrapping LangGraph compiled graphs
├── checkpoint.py        # CheckpointManager aligning LangGraph checkpoints with events
└── decorators.py        # @kernel_node decorator for determinism annotation
```

### 3.3 New Module: `core/projection/`

```
noesium/core/projection/
├── __init__.py          # Public exports: BaseProjection, ProjectionEngine
├── base.py              # BaseProjection[TState] ABC, ProjectionEngine
├── execution.py         # ExecutionProjection for workflow state
├── cognitive.py         # CognitiveProjection for conversation/reasoning traces
└── semantic.py          # SemanticProjection wrapping vector store indexing
```

### 3.4 New Module: `core/capability/`

```
noesium/core/capability/
├── __init__.py          # Public exports: Capability, CapabilityRegistry
├── models.py            # Capability, DeterminismClass, SideEffectClass, LatencyClass
├── registry.py          # CapabilityRegistry (projection-based)
├── discovery.py         # DiscoveryService for capability queries
└── resolution.py        # DeterministicResolver for capability selection
```

### 3.5 Modified Module: `core/msgbus/`

Add bridge module:

```
noesium/core/msgbus/
├── __init__.py          # Add EnvelopeBridge to exports
├── base.py              # Existing: BaseWatchdog, EventProcessor
└── bridge.py            # NEW: EnvelopeBridge (bubus ↔ EventEnvelope)
```

### 3.6 Modified Module: `core/memory/`

Add event-sourced memory classes:

```
noesium/core/memory/
├── __init__.py          # Add new exports
├── base.py              # Existing: BaseMemoryStore, BaseMemoryManager
├── models.py            # Existing: MemoryItem, MemoryFilter
├── ephemeral.py         # NEW: EphemeralMemory (session-scoped)
├── durable.py           # NEW: DurableMemory (event-sourced)
├── semantic.py          # NEW: SemanticMemory (vector-indexed)
├── manager.py           # NEW: MemoryManager (unified interface)
└── memu/                # Existing: Memu subsystem
```

---

## 4. Core Types

### 4.1 Event Envelope (RFC-0002 implementation)

```python
# core/event/envelope.py
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from uuid_utils import uuid7

class AgentRef(BaseModel):
    agent_id: str
    agent_type: str
    runtime_id: str = "local"
    instance_id: str = Field(default_factory=lambda: str(uuid7()))

class TraceContext(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid7()))
    span_id: str = Field(default_factory=lambda: str(uuid7()))
    parent_span_id: str | None = None
    depth: int = 0

    def child(self) -> "TraceContext":
        return TraceContext(
            trace_id=self.trace_id,
            parent_span_id=self.span_id,
            depth=self.depth + 1,
        )

class SignatureBlock(BaseModel):
    algorithm: str
    public_key_id: str
    signature: str

class EventEnvelope(BaseModel):
    spec_version: str = "1.0.0"
    event_id: str = Field(default_factory=lambda: str(uuid7()))
    event_type: str
    event_version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    producer: AgentRef
    trace: TraceContext
    causation_id: str | None = None
    correlation_id: str | None = None
    idempotency_key: str | None = None
    partition_key: str | None = None
    ttl_ms: int | None = None
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)
    signature: SignatureBlock | None = None
```

### 4.2 Domain Event Base

```python
# core/event/types.py
from abc import ABC, abstractmethod
from pydantic import BaseModel

class DomainEvent(BaseModel, ABC):
    @abstractmethod
    def event_type(self) -> str: ...

    def payload(self) -> dict[str, Any]:
        return self.model_dump(exclude={"event_type"})

    def to_envelope(
        self, producer: AgentRef, trace: TraceContext,
        causation_id: str | None = None, correlation_id: str | None = None,
    ) -> EventEnvelope:
        return EventEnvelope(
            event_type=self.event_type(),
            producer=producer,
            trace=trace,
            causation_id=causation_id,
            correlation_id=correlation_id,
            payload=self.payload(),
        )
```

### 4.3 Standard Domain Events

```python
# core/event/types.py (continued)

class AgentStarted(DomainEvent):
    agent_id: str
    agent_type: str
    def event_type(self) -> str: return "agent.started"

class NodeEntered(DomainEvent):
    node_id: str
    graph_id: str
    def event_type(self) -> str: return "kernel.node.entered"

class NodeCompleted(DomainEvent):
    node_id: str
    graph_id: str
    duration_ms: float
    def event_type(self) -> str: return "kernel.node.completed"

class CheckpointCreated(DomainEvent):
    checkpoint_id: str
    node_id: str
    def event_type(self) -> str: return "kernel.checkpoint.created"

class CapabilityRegistered(DomainEvent):
    capability_id: str
    version: str
    agent_id: str
    def event_type(self) -> str: return "capability.registered"

class CapabilityInvoked(DomainEvent):
    caller_agent_id: str
    target_agent_id: str
    capability_id: str
    def event_type(self) -> str: return "capability.invoked"

class MemoryWritten(DomainEvent):
    key: str
    value_type: str
    def event_type(self) -> str: return "memory.written"

class TaskRequested(DomainEvent):
    task_id: str
    capability_id: str
    payload: dict[str, Any] = {}
    def event_type(self) -> str: return "task.requested"

class TaskCompleted(DomainEvent):
    task_id: str
    result: Any = None
    error: str | None = None
    def event_type(self) -> str: return "task.completed"
```

---

## 5. Key Interfaces

### 5.1 EventStore

```python
# core/event/store.py
from abc import ABC, abstractmethod

class EventStore(ABC):
    @abstractmethod
    async def append(self, envelope: EventEnvelope) -> None: ...

    @abstractmethod
    async def read(
        self, from_offset: int = 0, limit: int | None = None,
        event_type: str | None = None, correlation_id: str | None = None,
    ) -> list[EventEnvelope]: ...

    @abstractmethod
    async def last_offset(self) -> int: ...

    @abstractmethod
    async def read_by_correlation(self, correlation_id: str) -> list[EventEnvelope]: ...


class InMemoryEventStore(EventStore):
    def __init__(self):
        self._events: list[EventEnvelope] = []

    async def append(self, envelope: EventEnvelope) -> None:
        self._events.append(envelope)

    async def read(self, from_offset=0, limit=None, event_type=None, correlation_id=None):
        events = self._events[from_offset:]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if correlation_id:
            events = [e for e in events if e.correlation_id == correlation_id]
        if limit:
            events = events[:limit]
        return events

    async def last_offset(self) -> int:
        return len(self._events)

    async def read_by_correlation(self, correlation_id: str):
        return [e for e in self._events if e.correlation_id == correlation_id]
```

### 5.2 KernelExecutor

```python
# core/kernel/executor.py
class KernelExecutor:
    def __init__(
        self,
        graph: CompiledStateGraph,
        event_store: EventStore,
        bridge: EnvelopeBridge,
        agent_ref: AgentRef,
    ):
        self._graph = graph
        self._event_store = event_store
        self._bridge = bridge
        self._agent_ref = agent_ref
        self._trace = TraceContext()

    async def execute(self, initial_state: dict, config: RunnableConfig | None = None):
        correlation_id = str(uuid7())
        self._trace = TraceContext()

        await self._emit(AgentStarted(
            agent_id=self._agent_ref.agent_id,
            agent_type=self._agent_ref.agent_type,
        ), correlation_id=correlation_id)

        result = await self._graph.ainvoke(initial_state, config=config)

        pending = result.pop("_pending_events", [])
        for event in pending:
            await self._emit(event, correlation_id=correlation_id)

        return result

    async def _emit(self, event: DomainEvent, correlation_id: str | None = None):
        envelope = event.to_envelope(
            producer=self._agent_ref,
            trace=self._trace,
            correlation_id=correlation_id,
        )
        await self._event_store.append(envelope)
        if self._bridge:
            await self._bridge.publish(envelope)
```

### 5.3 BaseProjection

```python
# core/projection/base.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Iterable

TState = TypeVar("TState")

class BaseProjection(ABC, Generic[TState]):
    @abstractmethod
    def initial_state(self) -> TState: ...

    @abstractmethod
    def apply(self, state: TState, event: EventEnvelope) -> TState: ...

    def fold(self, events: Iterable[EventEnvelope]) -> TState:
        state = self.initial_state()
        for event in events:
            state = self.apply(state, event)
        return state


class ProjectionEngine:
    def __init__(self, event_store: EventStore):
        self._event_store = event_store
        self._projections: dict[str, BaseProjection] = {}
        self._cache: dict[str, Any] = {}
        self._offsets: dict[str, int] = {}

    def register(self, name: str, projection: BaseProjection) -> None:
        self._projections[name] = projection
        self._cache[name] = projection.initial_state()
        self._offsets[name] = 0

    async def get_state(self, name: str) -> Any:
        projection = self._projections[name]
        current_offset = self._offsets[name]
        new_events = await self._event_store.read(from_offset=current_offset)
        state = self._cache[name]
        for event in new_events:
            state = projection.apply(state, event)
        self._cache[name] = state
        self._offsets[name] = current_offset + len(new_events)
        return state

    async def rebuild(self, name: str) -> Any:
        projection = self._projections[name]
        all_events = await self._event_store.read()
        state = projection.fold(all_events)
        self._cache[name] = state
        self._offsets[name] = len(all_events)
        return state
```

### 5.4 CapabilityRegistry

```python
# core/capability/registry.py
class CapabilityRegistry:
    def __init__(self, projection_engine: ProjectionEngine, bridge: EnvelopeBridge | None = None):
        self._engine = projection_engine
        self._bridge = bridge
        self._engine.register("capabilities", CapabilityProjection())

    async def register(self, agent_ref: AgentRef, capability: Capability) -> None:
        event = CapabilityRegistered(
            capability_id=capability.id,
            version=capability.version,
            agent_id=agent_ref.agent_id,
        )
        if self._bridge:
            envelope = event.to_envelope(producer=agent_ref, trace=TraceContext())
            await self._bridge.publish(envelope)

    async def find(self, capability_id: str, version_range: str | None = None):
        state = await self._engine.get_state("capabilities")
        matches = [
            (ref, cap) for ref, cap in state.entries
            if cap.id == capability_id
        ]
        if version_range:
            matches = [(r, c) for r, c in matches if _version_compatible(c.version, version_range)]
        return matches

    async def resolve(self, capability_id: str, version_range: str | None = None):
        matches = await self.find(capability_id, version_range)
        if not matches:
            return None
        # Deterministic: sort by registration order, pick first
        return matches[0]
```

### 5.5 MemoryManager

```python
# core/memory/manager.py
class MemoryManager:
    def __init__(
        self,
        ephemeral: EphemeralMemory | None = None,
        durable: DurableMemory | None = None,
        semantic: SemanticMemory | None = None,
    ):
        self._ephemeral = ephemeral or EphemeralMemory()
        self._durable = durable
        self._semantic = semantic

    async def store(self, key: str, value: Any, durable: bool = True, index: bool = False):
        self._ephemeral.set(key, value)
        if durable and self._durable:
            await self._durable.write(key, value)
        if index and self._semantic and isinstance(value, str):
            await self._semantic.index(key, value)

    async def recall(self, key: str) -> Any | None:
        result = self._ephemeral.get(key)
        if result is None and self._durable:
            result = await self._durable.read(key)
        return result

    async def search(self, query: str, top_k: int = 5):
        if self._semantic:
            return await self._semantic.search(query, top_k)
        return []
```

---

## 6. Implementation Details

### 6.1 EnvelopeBridge (bubus ↔ EventEnvelope)

```python
# core/msgbus/bridge.py
from bubus import BaseEvent, EventBus

class EnvelopeEvent(BaseEvent):
    """Bubus event wrapping an EventEnvelope."""
    envelope: EventEnvelope

class EnvelopeBridge:
    def __init__(self, event_bus: EventBus, event_store: EventStore):
        self._bus = event_bus
        self._store = event_store

    async def publish(self, envelope: EventEnvelope) -> None:
        await self._store.append(envelope)
        bubus_event = EnvelopeEvent(envelope=envelope)
        await self._bus.emit(bubus_event)

    async def subscribe(self, event_type: str, handler: Callable):
        async def wrapper(event: EnvelopeEvent):
            if event.envelope.event_type == event_type:
                await handler(event.envelope)
        self._bus.on(EnvelopeEvent, wrapper)
```

### 6.2 FileEventStore

```python
# core/event/store.py (additional implementation)
import json
from pathlib import Path

class FileEventStore(EventStore):
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    async def append(self, envelope: EventEnvelope) -> None:
        with open(self._path, "a") as f:
            f.write(envelope.model_dump_json() + "\n")

    async def read(self, from_offset=0, limit=None, event_type=None, correlation_id=None):
        if not self._path.exists():
            return []
        events = []
        with open(self._path) as f:
            for i, line in enumerate(f):
                if i < from_offset:
                    continue
                envelope = EventEnvelope.model_validate_json(line.strip())
                if event_type and envelope.event_type != event_type:
                    continue
                if correlation_id and envelope.correlation_id != correlation_id:
                    continue
                events.append(envelope)
                if limit and len(events) >= limit:
                    break
        return events
```

### 6.3 Kernel Node Decorator

```python
# core/kernel/decorators.py
import functools
from typing import Literal

def kernel_node(
    deterministic: bool = True,
    entropy_sources: list[str] | None = None,
):
    """Annotate a graph node with determinism metadata."""
    def decorator(func):
        func._kernel_meta = {
            "deterministic": deterministic,
            "entropy_sources": entropy_sources or [],
        }
        @functools.wraps(func)
        async def wrapper(self, state, config=None):
            return await func(self, state, config)
        wrapper._kernel_meta = func._kernel_meta
        return wrapper
    return decorator
```

---

## 7. Error Handling

### 7.1 Exception Hierarchy

```python
# core/event/exceptions.py (or a shared core/exceptions.py)
class NoesiumError(Exception):
    """Base exception."""

class EventError(NoesiumError): ...
class EventValidationError(EventError): ...
class EventStoreError(EventError): ...

class KernelError(NoesiumError): ...
class NodeExecutionError(KernelError): ...
class CheckpointError(KernelError): ...

class ProjectionError(NoesiumError): ...
class ProjectionVersionError(ProjectionError): ...

class CapabilityError(NoesiumError): ...
class CapabilityNotFoundError(CapabilityError): ...

class MemoryError(NoesiumError): ...
```

### 7.2 Error Event Emission

All errors in kernel execution SHOULD produce error events:

```python
class ErrorOccurred(DomainEvent):
    error_type: str
    message: str
    original_event_id: str | None = None
    stack_trace: str | None = None
    def event_type(self) -> str: return "system.error.occurred"
```

---

## 8. Configuration

### 8.1 Agent-Level Configuration

```python
class AgentConfig(BaseModel):
    agent_id: str | None = None
    llm_provider: str = "openai"
    llm_model: str | None = None
    execution_mode: str = "pragmatic"      # strict | pragmatic | sandbox
    event_store_backend: str = "memory"    # memory | file | postgres
    event_store_path: str | None = None    # For file backend
    enable_projections: bool = False
    enable_capabilities: bool = False
    enable_tracing: bool = True
```

### 8.2 Framework-Level Configuration

```python
class NoesiumConfig(BaseModel):
    runtime_id: str = "local"
    event_bus_backend: str = "bubus"
    log_level: str = "INFO"
    default_execution_mode: str = "pragmatic"
```

### 8.3 Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `NOESIUM_RUNTIME_ID` | Runtime identifier for agent refs | `"local"` |
| `NOESIUM_EXECUTION_MODE` | Default execution mode | `"pragmatic"` |
| `NOESIUM_EVENT_STORE` | Event store backend | `"memory"` |
| `NOESIUM_EVENT_STORE_PATH` | Path for file-based event store | `None` |

---

## 9. Testing Strategy

### 9.1 Unit Tests

Each new module MUST have corresponding tests:

| Module | Test File | Key Tests |
|--------|-----------|-----------|
| `event/envelope.py` | `tests/core/test_envelope.py` | Serialization, validation, canonicalization |
| `event/store.py` | `tests/core/test_event_store.py` | Append, read, filtering, offset tracking |
| `event/types.py` | `tests/core/test_domain_events.py` | Event creation, envelope conversion |
| `kernel/executor.py` | `tests/core/test_kernel.py` | Execution, event emission, resume |
| `projection/base.py` | `tests/core/test_projection.py` | Fold, incremental update, rebuild |
| `capability/registry.py` | `tests/core/test_capability.py` | Register, find, resolve |
| `memory/manager.py` | `tests/core/test_memory_manager.py` | Store, recall, search |

### 9.2 Integration Tests

* Event flow: agent → event store → projection → state verification
* Kernel execution: graph compile → execute → event emission → checkpoint
* Capability flow: register → discover → resolve → invoke

### 9.3 Replay Tests

* Emit events → rebuild projection → verify state matches
* Execute graph → replay from event log → verify deterministic outcome

---

## 10. Migration Strategy

### Phase 1: Event Infrastructure (Non-breaking)

1. Add `core/event/` module with `EventEnvelope`, `EventStore`, `InMemoryEventStore`
2. Add `core/msgbus/bridge.py` with `EnvelopeBridge`
3. No changes to existing agent code
4. Export from `core/__init__.py`

### Phase 2: Kernel Wrapper (Opt-in)

1. Add `core/kernel/` module with `KernelExecutor`
2. Add `@kernel_node` decorator
3. Modify `BaseGraphicAgent` to optionally use `KernelExecutor` (gated by `execution_mode`)
4. Existing agents work unchanged

### Phase 3: Projection Layer (Opt-in)

1. Add `core/projection/` module
2. Add `core/memory/{ephemeral,durable,semantic,manager}.py`
3. Modify `BaseAgent` to optionally initialize projection engine and memory manager
4. Gated by `enable_projections` configuration

### Phase 4: Capability Registry (Opt-in)

1. Add `core/capability/` module
2. Add `declare_capability()` to `BaseGraphicAgent`
3. Gated by `enable_capabilities` configuration
