# GraphMemoryProvider Implementation Architecture

> Implementation guide for graph-based memory provider in Noesium.
>
> **Module**: `noesium/core/memory/providers/graph.py`
> **Source**: Derived from [RFC-2001](../../specs/RFC-2001.md) §10, [RFC-2002](../../specs/RFC-2002.md) §6.4
> **Related RFCs**: [RFC-0004](../../specs/RFC-0004.md), [RFC-2001](../../specs/RFC-2001.md), [RFC-2002](../../specs/RFC-2002.md)
> **Language**: Python 3.11+
> **Framework**: Pydantic v2, NetworkX (initial implementation)

---

## 1. Overview

GraphMemoryProvider implements the graph-based memory contract defined in RFC-2001 §10. It stores entity-relation triples, enabling long-running agents to accumulate structured knowledge about people, concepts, projects, and their relationships.

### 1.1 Purpose

This implementation guide specifies:

- Entity and relation data models
- Graph storage backend (NetworkX for v1, with extensibility for Neo4j/etc.)
- MemoryProvider protocol compliance
- Graph traversal and query operations
- Event emission for all graph mutations
- Integration with existing MemoryManager

### 1.2 Scope

**In Scope**:
- `GraphMemoryProvider` class implementing `MemoryProvider`
- Entity and relation Pydantic models
- Graph traversal operations
- Event-sourced writes
- NetworkX in-memory implementation
- File-based persistence for graph state

**Out of Scope**:
- Neo4j or other external graph database integration (future)
- Graph schema enforcement (future)
- Graph embedding/indexing for semantic search
- Multi-agent graph sharing protocol

### 1.3 Spec Compliance

This guide **MUST NOT** contradict RFC-2001 §10 (Graph Memory Contract) or RFC-2002 §6.4 (GraphMemoryProvider stub). All graph operations specified in RFC-2001 §10 table must be implemented.

---

## 2. Architectural Position

### 2.1 System Context

```
┌─────────────────────────────────────────────────────────┐
│                   MemoryManager                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │  Working    │  │ EventSourced │  │     Graph      │ │
│  │  Provider   │  │   Provider   │  │    Provider    │ │
│  └─────────────┘  └──────────────┘  └────────┬───────┘ │
│                                               │         │
│  ┌────────────────────────────────────────────▼────────┐│
│  │              Graph Storage Layer                    ││
│  │  NetworkX DiGraph + File Persistence               ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### 2.2 Dependency Graph

```
GraphMemoryProvider
├── noesium.core.memory.provider.MemoryProvider (protocol)
├── noesium.core.memory.provider.ProviderCapabilities
├── noesium.core.event.store.EventStore
├── noesium.core.event.types.MemoryWritten, MemoryLinked
├── networkx.DiGraph (graph structure)
└── pydantic.BaseModel
```

### 2.3 Module Responsibilities

| Module | Responsibility | Dependencies |
|--------|----------------|--------------|
| `providers/graph.py` | GraphMemoryProvider class, entity/relation models | NetworkX, EventStore |
| `memory/events.py` | MemoryLinked event type | EventEnvelope |
| (existing) `provider_manager.py` | Register graph provider | GraphMemoryProvider |

---

## 3. Module Structure

```
noesium/core/memory/
├── providers/
│   ├── graph.py           # NEW: GraphMemoryProvider implementation
│   ├── working.py         # (existing)
│   ├── event_sourced.py   # (existing)
│   └── memu.py            # (existing)
├── events.py              # ADD: MemoryLinked event
└── ...
```

---

## 4. Core Types

### 4.1 Entity Model

```python
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

class EntityType(str, Enum):
    """Predefined entity types for graph memory."""
    PERSON = "person"
    PROJECT = "project"
    CONCEPT = "concept"
    ORGANIZATION = "organization"
    LOCATION = "location"
    EVENT = "event"
    DOCUMENT = "document"
    TOOL = "tool"
    AGENT = "agent"
    CUSTOM = "custom"

class GraphEntity(BaseModel):
    """Entity node in the graph (RFC-2001 §10)."""
    entity_id: str = Field(default_factory=lambda: f"entity-{uuid4().hex[:12]}")
    entity_type: EntityType = EntityType.CUSTOM
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime | None = None
    source_event_id: str | None = None  # Traceability to creating event

    def to_memory_value(self) -> dict[str, Any]:
        """Serialize for MemoryEntry.value."""
        return self.model_dump()
```

### 4.2 Relation Model

```python
class RelationType(str, Enum):
    """Predefined relation types."""
    # Hierarchical
    PART_OF = "part_of"
    HAS_SUBPROJECT = "has_subproject"
    BELONGS_TO = "belongs_to"

    # Social
    KNOWS = "knows"
    WORKS_WITH = "works_with"
    REPORTS_TO = "reports_to"

    # Causal
    CAUSED_BY = "caused_by"
    DEPENDS_ON = "depends_on"
    ENABLES = "enables"

    # Temporal
    PRECEDES = "precedes"
    FOLLOWS = "follows"

    # Semantic
    RELATED_TO = "related_to"
    SAME_AS = "same_as"
    DIFFERENT_FROM = "different_from"

    # Custom
    CUSTOM = "custom"

class GraphRelation(BaseModel):
    """Directed edge between entities (RFC-2001 §10)."""
    relation_id: str = Field(default_factory=lambda: f"rel-{uuid4().hex[:12]}")
    source_id: str
    target_id: str
    relation_type: RelationType = RelationType.RELATED_TO
    properties: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    source_event_id: str | None = None
```

### 4.3 Traversal Query

```python
class TraversalPattern(str, Enum):
    """Graph traversal patterns."""
    BFS = "bfs"  # Breadth-first search
    DFS = "dfs"  # Depth-first search
    SHORTEST_PATH = "shortest_path"
    ALL_PATHS = "all_paths"
    NEIGHBORS = "neighbors"

class GraphTraversal(BaseModel):
    """Graph traversal query specification."""
    start_entity_id: str
    pattern: TraversalPattern = TraversalPattern.BFS
    relation_types: list[RelationType] | None = None  # Filter by relation types
    entity_types: list[EntityType] | None = None  # Filter by entity types
    max_depth: int = 2
    limit: int = 100
    direction: Literal["outgoing", "incoming", "both"] = "outgoing"
```

---

## 5. Key Interfaces

### 5.1 GraphMemoryProvider

```python
from noesium.core.memory.provider import (
    MemoryProvider,
    MemoryEntry,
    ProviderCapabilities,
    MemoryTier,
    RecallResult,
)
from noesium.core.event.store import EventStore
from noesium.core.event.envelope import AgentRef, TraceContext
from noesium.core.event.types import MemoryWritten, MemoryLinked
import networkx as nx
from pathlib import Path
import json

class GraphMemoryProvider(MemoryProvider):
    """Graph-based memory provider (RFC-2001 §10, RFC-2002 §6.4)."""

    def __init__(
        self,
        event_store: EventStore | None = None,
        producer: AgentRef | None = None,
        persistence_path: Path | None = None,
    ) -> None:
        """Initialize graph provider.

        Args:
            event_store: Optional event store for emitting graph mutation events
            producer: Agent reference for event envelopes
            persistence_path: Optional path to persist graph state as JSON
        """
        self._store = event_store
        self._producer = producer
        self._trace = TraceContext()
        self._persistence_path = persistence_path
        self._graph: nx.DiGraph = nx.DiGraph()

        if persistence_path and persistence_path.exists():
            self._load_from_file(persistence_path)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id="graph",
            tier=MemoryTier.PERSISTENT,
            supports_search=True,
            supports_graph=True,
            content_types=["entity"],
        )

    # ------------------------------------------------------------------
    # Graph-specific operations (RFC-2001 §10)
    # ------------------------------------------------------------------

    async def add_entity(
        self,
        entity: GraphEntity,
    ) -> MemoryEntry:
        """Add or update an entity node.

        Emits MemoryWritten event with content_type="entity".
        """
        entity.updated_at = datetime.now(tz=timezone.utc)
        self._graph.add_node(
            entity.entity_id,
            **entity.to_memory_value()
        )

        if self._store and self._producer:
            event = MemoryWritten(
                key=entity.entity_id,
                value=entity.to_memory_value(),
                value_type="GraphEntity",
                content_type="entity",
                provider_id="graph",
            )
            envelope = event.to_envelope(producer=self._producer, trace=self._trace)
            await self._store.append(envelope)
            entity.source_event_id = envelope.event_id

        if self._persistence_path:
            self._save_to_file(self._persistence_path)

        return MemoryEntry(
            key=entity.entity_id,
            value=entity.to_memory_value(),
            content_type="entity",
            provider_id="graph",
        )

    async def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType = RelationType.RELATED_TO,
        properties: dict[str, Any] | None = None,
        weight: float = 1.0,
    ) -> None:
        """Add a directed edge between entities.

        Emits MemoryLinked event.

        Raises:
            ValueError: If source_id or target_id don't exist in graph
        """
        if source_id not in self._graph:
            raise ValueError(f"Source entity {source_id} not found")
        if target_id not in self._graph:
            raise ValueError(f"Target entity {target_id} not found")

        relation = GraphRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            properties=properties or {},
            weight=weight,
        )

        self._graph.add_edge(
            source_id,
            target_id,
            **relation.model_dump()
        )

        if self._store and self._producer:
            event = MemoryLinked(
                source_key=source_id,
                target_key=target_id,
                relation=relation_type.value,
            )
            envelope = event.to_envelope(producer=self._producer, trace=self._trace)
            await self._store.append(envelope)
            relation.source_event_id = envelope.event_id

        if self._persistence_path:
            self._save_to_file(self._persistence_path)

    async def get_entity(self, entity_id: str) -> GraphEntity | None:
        """Retrieve an entity by ID."""
        if entity_id not in self._graph:
            return None
        data = self._graph.nodes[entity_id]
        return GraphEntity(**data)

    async def get_relations(
        self,
        entity_id: str,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
        relation_type: RelationType | None = None,
    ) -> list[GraphRelation]:
        """Get relations for an entity.

        Args:
            entity_id: Entity to query
            direction: 'outgoing' (edges from entity), 'incoming' (edges to entity), 'both'
            relation_type: Optional filter by relation type
        """
        relations: list[GraphRelation] = []

        if direction in ("outgoing", "both"):
            for _, target, data in self._graph.out_edges(entity_id, data=True):
                rel = GraphRelation(**data)
                if relation_type is None or rel.relation_type == relation_type:
                    relations.append(rel)

        if direction in ("incoming", "both"):
            for source, _, data in self._graph.in_edges(entity_id, data=True):
                rel = GraphRelation(**data)
                if relation_type is None or rel.relation_type == relation_type:
                    relations.append(rel)

        return relations

    async def traverse(
        self,
        traversal: GraphTraversal,
    ) -> list[GraphEntity]:
        """Execute graph traversal query."""
        if traversal.start_entity_id not in self._graph:
            return []

        if traversal.pattern == TraversalPattern.NEIGHBORS:
            # Direct neighbors only
            neighbor_ids = set()
            if traversal.direction in ("outgoing", "both"):
                neighbor_ids.update(self._graph.successors(traversal.start_entity_id))
            if traversal.direction in ("incoming", "both"):
                neighbor_ids.update(self._graph.predecessors(traversal.start_entity_id))
            entities = [await self.get_entity(eid) for eid in neighbor_ids]
            return [e for e in entities if e is not None][:traversal.limit]

        elif traversal.pattern == TraversalPattern.BFS:
            # Breadth-first traversal
            visited = set()
            queue = [traversal.start_entity_id]
            result = []

            while queue and len(result) < traversal.limit:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)

                if current != traversal.start_entity_id:
                    entity = await self.get_entity(current)
                    if entity:
                        result.append(entity)

                if len(visited) < traversal.max_depth + 1:
                    neighbors = list(self._graph.successors(current))
                    queue.extend(neighbors)

            return result

        elif traversal.pattern == TraversalPattern.DFS:
            # Depth-first traversal
            visited = set()
            result = []

            def dfs(node_id: str, depth: int):
                if len(result) >= traversal.limit or depth > traversal.max_depth:
                    return
                if node_id in visited:
                    return
                visited.add(node_id)

                if node_id != traversal.start_entity_id:
                    entity = asyncio.get_event_loop().run_until_complete(
                        self.get_entity(node_id)
                    )
                    if entity:
                        result.append(entity)

                for neighbor in self._graph.successors(node_id):
                    dfs(neighbor, depth + 1)

            dfs(traversal.start_entity_id, 0)
            return result

        else:
            raise NotImplementedError(f"Traversal pattern {traversal.pattern} not yet implemented")

    # ------------------------------------------------------------------
    # MemoryProvider protocol implementation
    # ------------------------------------------------------------------

    async def write(
        self,
        key: str,
        value: Any,
        *,
        content_type: str = "entity",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Write entity to graph (MemoryProvider protocol)."""
        if content_type != "entity":
            raise ValueError(f"GraphMemoryProvider only supports content_type='entity', got {content_type}")

        if isinstance(value, GraphEntity):
            entity = value
        elif isinstance(value, dict):
            entity = GraphEntity(**value)
        else:
            raise TypeError(f"value must be GraphEntity or dict, got {type(value)}")

        # Override entity_id with key if different
        if entity.entity_id != key:
            entity.entity_id = key

        return await self.add_entity(entity)

    async def read(self, key: str) -> MemoryEntry | None:
        """Read entity by ID (MemoryProvider protocol)."""
        entity = await self.get_entity(key)
        if entity is None:
            return None
        return MemoryEntry(
            key=entity.entity_id,
            value=entity.to_memory_value(),
            content_type="entity",
            provider_id="graph",
        )

    async def delete(self, key: str) -> bool:
        """Remove entity and all its relations."""
        if key not in self._graph:
            return False

        self._graph.remove_node(key)

        if self._persistence_path:
            self._save_to_file(self._persistence_path)

        return True

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        content_types: list[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[RecallResult]:
        """Search entities by name (simple substring match)."""
        results: list[RecallResult] = []
        query_lower = query.lower()

        for node_id, data in self._graph.nodes(data=True):
            name = str(data.get("name", ""))
            entity_type = data.get("entity_type", "custom")

            if content_types and "entity" not in content_types:
                continue

            if query_lower in name.lower():
                entity = GraphEntity(**data)
                results.append(
                    RecallResult(
                        entry=MemoryEntry(
                            key=node_id,
                            value=data,
                            content_type="entity",
                            provider_id="graph",
                        ),
                        score=0.8,
                        provider_id="graph",
                        tier=MemoryTier.PERSISTENT,
                    )
                )

        return results[:limit]

    async def list_keys(
        self,
        *,
        content_types: list[str] | None = None,
        prefix: str | None = None,
    ) -> list[str]:
        """List all entity IDs."""
        keys = list(self._graph.nodes())
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        return keys

    async def rebuild(self) -> None:
        """Rebuild graph from event log."""
        if not self._store:
            return

        self._graph.clear()
        events = await self._store.read(event_type="memory.written")

        for envelope in events:
            if envelope.payload.get("provider_id") != "graph":
                continue
            entity_data = envelope.payload.get("value")
            if entity_data:
                entity = GraphEntity(**entity_data)
                self._graph.add_node(entity.entity_id, **entity.to_memory_value())

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _save_to_file(self, path: Path) -> None:
        """Save graph state to JSON file."""
        data = nx.node_link_data(self._graph)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_from_file(self, path: Path) -> None:
        """Load graph state from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)
        self._graph = nx.node_link_graph(data, directed=True)

    async def close(self) -> None:
        """Persist graph before closing."""
        if self._persistence_path:
            self._save_to_file(self._persistence_path)
```

---

## 6. Implementation Details

### 6.1 Event Types

Add to `noesium/core/event/types.py`:

```python
class MemoryLinked(DomainEvent):
    """Emitted when two entities are linked in graph memory (RFC-2001 §8)."""
    source_key: str
    target_key: str
    relation: str

    def event_type(self) -> str:
        return "memory.linked"
```

### 6.2 Integration with NoeAgent

Update `noesium/agents/noe/agent.py`:

```python
async def _setup_memory(self) -> None:
    providers = []
    if "working" in self.config.memory_providers:
        providers.append(WorkingMemoryProvider())
    if "event_sourced" in self.config.memory_providers:
        producer = AgentRef(agent_id=self._agent_id, agent_type="noe")
        providers.append(EventSourcedProvider(self._event_store, producer))
    if "graph" in self.config.memory_providers:  # NEW
        producer = AgentRef(agent_id=self._agent_id, agent_type="noe")
        providers.append(GraphMemoryProvider(
            event_store=self._event_store,
            producer=producer,
            persistence_path=Path.home() / ".noesium" / "memory" / f"{self._agent_id}_graph.json",
        ))
    self._memory_manager = ProviderMemoryManager(providers)
```

Update `NoeConfig`:

```python
memory_providers: list[str] = Field(
    default_factory=lambda: ["working", "event_sourced", "graph"],  # Add graph
)
```

---

## 7. Error Handling

```python
class GraphMemoryError(NoesiumError):
    """Base graph memory exception."""

class EntityNotFoundError(GraphMemoryError):
    """Requested entity does not exist in graph."""

class RelationNotFoundError(GraphMemoryError):
    """Requested relation does not exist."""

class InvalidTraversalError(GraphMemoryError):
    """Invalid traversal parameters."""
```

| Error Category | Handling Approach |
|----------------|-------------------|
| Entity not found | Return `None` or empty list (graceful) |
| Invalid relation (missing nodes) | Raise `ValueError` with clear message |
| Traversal failure | Log warning, return empty result |
| Persistence failure | Log error, continue in-memory |
| Event emission failure | Log warning, continue without event |

---

## 8. Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `event_store` | `EventStore \| None` | `None` | Event store for mutation events |
| `producer` | `AgentRef \| None` | `None` | Agent reference for events |
| `persistence_path` | `Path \| None` | `None` | File path for graph persistence |
| `max_graph_size` | `int` | `10000` | Maximum nodes before eviction (future) |

---

## 9. Testing Strategy

### 9.1 Unit Tests

| Test | Coverage |
|------|----------|
| `test_add_entity` | Entity added to graph, event emitted |
| `test_add_relation` | Relation added, MemoryLinked event emitted |
| `test_get_entity` | Entity retrieval by ID |
| `test_get_relations` | Outgoing/incoming/both relations |
| `test_traverse_bfs` | Breadth-first traversal |
| `test_traverse_dfs` | Depth-first traversal |
| `test_search` | Entity search by name |
| `test_persistence` | Save/load from file |
| `test_rebuild` | Rebuild from event log |

### 9.2 Integration Tests

| Test | Coverage |
|------|----------|
| `test_graph_in_memory_manager` | Register graph provider with MemoryManager |
| `test_graph_in_noe_agent` | NoeAgent with graph memory enabled |
| `test_multi_provider_recall` | Recall across working + event_sourced + graph |
| `test_event_sourced_replay` | Rebuild graph from event store |

---

## 10. Migration/Compatibility

### 10.1 Backward Compatibility

- GraphMemoryProvider is **opt-in** via configuration
- Existing agents without `"graph"` in `memory_providers` are unaffected
- No changes to existing provider implementations

### 10.2 Rollout

**Phase 1**: Core implementation (this guide)
- NetworkX-based in-memory graph
- File persistence
- Event emission

**Phase 2**: Agent integration
- Add to NoeConfig defaults
- Update NoeAgent initialization
- Add graph-specific tools (optional)

**Phase 3**: Advanced features
- Graph embeddings for semantic search
- Neo4j adapter
- Graph schema enforcement
- Multi-agent graph sharing

---

## Appendix A: RFC Requirement Mapping

| RFC Requirement | Guide Section | Implementation |
|-----------------|---------------|----------------|
| RFC-2001 §10 Entity model | §4.1 | `GraphEntity` Pydantic model |
| RFC-2001 §10 Relation model | §4.2 | `GraphRelation` Pydantic model |
| RFC-2001 §10 Traversal | §4.3, §5.1 | `GraphTraversal`, `traverse()` |
| RFC-2001 §10 `add_entity` | §5.1 | `add_entity()` method |
| RFC-2001 §10 `add_relation` | §5.1 | `add_relation()` method |
| RFC-2001 §10 `get_entity` | §5.1 | `get_entity()` method |
| RFC-2001 §10 `get_relations` | §5.1 | `get_relations()` method |
| RFC-2001 §8 `memory.linked` event | §6.1 | `MemoryLinked` event type |
| RFC-2002 §6.4 Provider stub | §5.1 | Full implementation |

---

## Appendix B: Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-02 | 1.0 | Initial implementation guide |