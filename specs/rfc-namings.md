# noesium Terminology Reference

Authoritative terminology reference for noesium RFC specifications.

**Last Updated**: 2026-03-01

---

## Rules

1. All RFCs **MUST** use the terms defined here when referring to project concepts
2. New terms introduced in an RFC **MUST** be registered in this document
3. Deprecated terms **MUST** be removed when the defining RFC is deprecated
4. This document reflects the **current** state of terminology (not historical)

---

## Terms

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| Agent Kernel | RFC-0001 §5.2 | Deterministic, graph-based execution runtime within each agent |
| AgentRef | RFC-0002 §5 | Producer identity structure containing agent_id, agent_type, runtime_id, instance_id |
| BaseAgent | RFC-1001 §11 | Abstract base class for all Noesium agents |
| BaseHitlAgent | RFC-1002 §5.2 | Base class for multi-turn conversation agents with HITL |
| BaseGraphicAgent | RFC-1001 §11 | Base class for LangGraph-based agents |
| BaseProjection | RFC-1001 §8.1 | Abstract generic projection: deterministic fold over event stream |
| BaseResearcher | RFC-1002 §5.3 | Base class for iterative research agents |
| Capability | RFC-0005 §4.1 | Typed contract declaring an agent's available functions |
| Capability Registry | RFC-0005 §4.3 | Projection-based registry for capability discovery |
| Causation ID | RFC-0002 §7.1 | References the event_id that directly caused an event |
| Checkpoint | RFC-0003 §10 | State snapshot at node boundaries for crash recovery |
| Cognitive Projection | RFC-0004 §4.3.2 | Deterministic structural projection for knowledge (conversation history, reasoning trace) |
| Conversation Agent | RFC-1002 §5.2 | Agent archetype for multi-turn HITL conversations |
| Correlation ID | RFC-0002 §7.2 | Logical grouping identifier shared by related events |
| Determinism Class | RFC-0005 §4.1 | Classification: deterministic or nondeterministic |
| Deterministic Kernel | RFC-0003 §3 | Execution substrate enforcing reproducibility via graph-based state transitions |
| Domain Event | RFC-1001 §6.2 | Typed business-level event that produces an EventEnvelope |
| Durable Memory | RFC-0004 §5.2 | Event-sourced canonical memory layer (task history, structured knowledge) |
| Envelope Bridge | RFC-1001 §6.4 | Bidirectional adapter between bubus BaseEvent and EventEnvelope |
| Ephemeral Memory | RFC-0004 §5.1 | Session-scoped working memory, cleared on restart |
| Event Bus | RFC-0001 §5.1 | Topic-based transport layer for inter-agent event routing |
| Event Envelope | RFC-0002 §3 | Canonical immutable structure wrapping every event in the system |
| Event Store | RFC-0001 §5.3 | Append-only event log per agent |
| Execution Mode | RFC-1001 §12.3 | Configuration: strict (event-mediated), pragmatic (direct), or sandbox |
| Execution Projection | RFC-0004 §4.3.1 | Strict deterministic projection for workflow state, task graph, retry counters |
| Federated Projection | RFC-0004 §6.3 | Composite projection across multiple agents |
| HITL | RFC-1002 §9 | Human-in-the-loop: interrupt/resume pattern for human interaction |
| Kernel Executor | RFC-1001 §7.1 | Wrapper over LangGraph with event emission and checkpointing |
| Memory Hierarchy | RFC-0004 §5 | Three-layer memory: ephemeral, durable, semantic |
| Memory Manager | RFC-1001 §9.4 | Unified interface composing all three memory layers |
| Node Result | RFC-1001 §7.1 | Output from a graph node: state_delta + emitted events |
| Partition Key | RFC-0002 §8.2 | Determines event stream partition for ordering guarantees |
| Projection | RFC-0004 §4.2 | Deterministic fold over event stream: P(State, Event) → State |
| Projection Engine | RFC-1001 §8.2 | Manages projection lifecycle: build, cache, invalidate, rebuild |
| Research Agent | RFC-1002 §5.3 | Agent archetype for iterative multi-step research |
| Semantic Memory | RFC-0004 §5.3 | Indexed retrieval layer derived from durable memory via embeddings |
| Semantic Projection | RFC-0004 §4.3.3 | Index-based projection constructed from deterministic projection output |
| Side-Effect Class | RFC-0005 §4.1 | Classification: pure, idempotent, or external |
| Signature Block | RFC-0002 §11 | Optional cryptographic signature covering the canonicalized envelope |
| State Graph | RFC-0003 §4 | Directed graph declaring workflow nodes and allowed transitions |
| Task Agent | RFC-1002 §5.4 | Agent archetype for linear or branching task execution |
| Toolify | RFC-1001 §12 | Tool system with registry, configuration, and MCP integration |
| Toolkit Registry | RFC-1001 §12 | Auto-discovery registry for built-in and custom toolkits |
| Trace Context | RFC-0002 §6 | Distributed tracing structure: trace_id, span_id, parent_span_id, depth |

---

## Usage Guidelines

- **Capitalization**: Use the capitalization shown in the Term column when referring to defined terms
- **First use**: On first use in an RFC, link to this document or the defining RFC
- **Synonyms**: Avoid synonyms; use the canonical term from this table

---

## Related Documents

- [rfc-standard.md](rfc-standard.md) - RFC process and conventions
- [rfc-index.md](rfc-index.md) - RFC index
- [rfc-history.md](rfc-history.md) - Change history
