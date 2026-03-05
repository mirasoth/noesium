# noesium Terminology Reference

Authoritative terminology reference for noesium RFC specifications.

**Last Updated**: 2026-03-05

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
| Agent Kernel Pod | RFC-1003 §5.1 | Control plane pod responsible for ToolCall generation, capability validation, and effect executor dispatch |
| AgentAction | RFC-1005 §12.1 | NoeAgent action model containing thought and exactly one of: tool_calls, subagent, or text_response |
| AgentRef | RFC-0002 §5 | Producer identity structure containing agent_id, agent_type, runtime_id, instance_id |
| AtomicTool | RFC-2003 §6 | Smallest executable unit in the tool system with schema and capability metadata |
| BaseAgent | RFC-1001 §11 | Abstract base class for all Noesium agents |
| BaseGraphicAgent | RFC-1001 §11 | Base class for LangGraph-based agents |
| BaseHitlAgent | RFC-1002 §5.2 | Base class for multi-turn conversation agents with HITL |
| BaseProjection | RFC-1001 §8.1 | Abstract generic projection: deterministic fold over event stream |
| BaseResearcher | RFC-1002 §5.3 | Base class for iterative research agents |
| BaseSubagentRuntime | RFC-1006 §5.5 | Protocol for subagent execution: invoke, invoke_stream, cancel, cleanup |
| Capability | RFC-0005 §4.1 | Typed contract declaring an agent's available functions |
| Capability Registry | RFC-0005 §4.3 | Projection-based registry for capability discovery |
| Causation ID | RFC-0002 §7.1 | References the event_id that directly caused an event |
| Checkpoint | RFC-0003 §10 | State snapshot at node boundaries for crash recovery |
| Cognitive Projection | RFC-0004 §4.3.2 | Deterministic structural projection for knowledge (conversation history, reasoning trace) |
| Conversation Agent | RFC-1002 §5.2 | Agent archetype for multi-turn HITL conversations |
| Correlation ID | RFC-0002 §7.2 | Logical grouping identifier shared by related events |
| Core Layer | RFC-1007 §5.3.1 | Framework primitives (noesium.core); zero knowledge of application |
| Dependency Direction | RFC-1007 §4 | Rule: core ← toolkits ← subagents ← noeagent; lower layers cannot import higher |
| Determinism Class | RFC-0005 §4.1 | Classification: deterministic or nondeterministic |
| Deterministic Kernel | RFC-0003 §3 | Execution substrate enforcing reproducibility via graph-based state transitions |
| Domain Event | RFC-1001 §6.2 | Typed business-level event that produces an EventEnvelope |
| Durable Memory | RFC-0004 §5.2 | Event-sourced canonical memory layer (task history, structured knowledge) |
| Effect Executor | RFC-0006 §5.2 | Isolated sandboxed unit that runs one ToolCall and returns EffectResult; distinct from Subagent (cognitive agent) |
| Effect Node | RFC-0006 §10 | Record of external tool execution with input hash, tool spec, metadata, output, and exit status |
| Effect Result | RFC-0006 §7 | Structured result returned from sandboxed tool execution containing tool_id, exit_code, output, and metadata |
| Envelope Bridge | RFC-1001 §6.4 | Bidirectional adapter between bubus BaseEvent and EventEnvelope |
| Ephemeral Memory | RFC-0004 §5.1 | Session-scoped working memory, cleared on restart |
| Event Bus | RFC-0001 §5.1 | Topic-based transport layer for inter-agent event routing |
| Event Envelope | RFC-0002 §3 | Canonical immutable structure wrapping every event in the system |
| Event Store | RFC-0001 §5.3 | Append-only event log per agent |
| EventSourcedProvider | RFC-2002 §6.2 | Persistent memory provider wrapping EventStore and CognitiveProjection |
| Execution Mode | RFC-1001 §12.3 | Configuration: strict (event-mediated), pragmatic (direct), or sandbox |
| GitHub Client | RFC-9001 §9.3 | Backend service for Git operations (clone, pull, commit, push) |
| Execution Projection | RFC-0004 §4.3.1 | Strict deterministic projection for workflow state, task graph, retry counters |
| Federated Projection | RFC-0004 §6.3 | Composite projection across multiple agents |
| FrameworkConfig | RFC-1007 §5.3.1 | Framework-level configuration (renamed from core config) |
| GraphMemoryProvider | RFC-2002 §6.4 | Future memory provider for entity-relation graph storage |
| HITL | RFC-1002 §9 | Human-in-the-loop: interrupt/resume pattern for human interaction |
| Indexed Memory | RFC-2001 §5.3 | Semantic search overlay tier derived from Persistent Memory |
| Kernel Executor | RFC-1001 §7.1 | Wrapper over LangGraph with event emission and checkpointing |
| Memory Entry | RFC-2002 §4.1 | Keyed memory record with content_type, metadata, and provider_id |
| Memory Hierarchy | RFC-0004 §5 | Three-layer memory: ephemeral, durable, semantic |
| Memory Manager | RFC-2002 §8 | Unified facade routing operations to registered memory providers |
| Memory Provider | RFC-2001 §6.1 | Abstract contract for memory backends with write/read/search/delete |
| Memory Tier | RFC-2001 §5 | Classification: working, persistent, or indexed |
| MemuProvider | RFC-2002 §6.3 | Persistent memory provider wrapping MemU file-based memory system |
| NoeCoder | RFC-9000 §1 | Personal coding assistant webserver built on NoeAgent |
| Node Result | RFC-1001 §7.1 | Output from a graph node: state_delta + emitted events |
| OpenSandbox Executor | RFC-1003 §5.3 | Data plane component providing hardened container isolation for tool execution |
| Partition Key | RFC-0002 §8.2 | Determines event stream partition for ordering guarantees |
| Persistent Memory | RFC-2001 §5.2 | Cross-session durable memory tier surviving restarts |
| Projection | RFC-0004 §4.2 | Deterministic fold over event stream: P(State, Event) → State |
| Projection Engine | RFC-1001 §8.2 | Manages projection lifecycle: build, cache, invalidate, rebuild |
| Projection Layer | RFC-0001 §5.4 | Derives current agent state from the event log |
| Recall Protocol | RFC-2001 §9 | Unified query interface across all memory providers with result merging |
| Recall Query | RFC-2002 §4.3 | Structured query with scope, content_types, and metadata filters |
| Repository | RFC-9001 §6.1 | Cloned Git repository with URL, local path, and sync state |
| Research Agent | RFC-1002 §5.3 | Agent archetype for iterative multi-step research |
| Semantic Memory | RFC-0004 §5.3 | Indexed retrieval layer derived from durable memory via embeddings |
| Semantic Projection | RFC-0004 §4.3.3 | Index-based projection constructed from deterministic projection output |
| Session | RFC-9001 §6.1 | NoeAgent execution session linked to a task |
| Session Manager | RFC-9001 §10.1 | Service managing NoeAgent instances per repository |
| Session Worker | RFC-1003 §5.2 | Logical worker representing a user session with memory namespace, execution stack, and capability scope |
| State Manager | RFC-9001 §9.4 | File-based persistence service for tasks, sessions, and configuration |
| Side-Effect Class | RFC-0005 §4.1 | Classification: pure, idempotent, or external |
| Signature Block | RFC-0002 §11 | Optional cryptographic signature covering the canonicalized envelope |
| Skill | RFC-2003 §9 | Named composition of AtomicTools with input/output contract and orchestration logic |
| Skill Registry | RFC-2004 §9 | Registry for skill discovery and management |
| State Graph | RFC-0003 §4 | Directed graph declaring workflow nodes and allowed transitions |
| Subagent | RFC-1005 §5.1 | Delegated cognitive agent (AGENT/CLI_AGENT); extends orchestrator's reasoning; stateful, session-scoped |
| SubagentAction | RFC-1005 §12.1 | NoeAgent action for spawning, interacting with, or terminating subagents |
| SubagentContext | RFC-1006 §5.6 | Context passed to subagents: session_id, parent_id, shared_memory, config |
| SubagentDescriptor | RFC-1006 §5.1 | Static metadata for discovery and planning (subagent_id, backend_type, task_types, etc.) |
| SubagentInvocationRequest | RFC-1006 §5.2 | Runtime request: request_id, subagent_id, message, context, execution_mode, timeout |
| SubagentInvocationResult | RFC-1006 §5.3 | Runtime result: success, final_text, structured_output, artifacts, error_code |
| SubagentManager | RFC-1006 §4 | Selection, invocation, and lifecycle management of subagents |
| SubagentProgressEvent | RFC-1006 §5.4 | Normalized stream event: SUBAGENT_START, PROGRESS, TOOL_CALL, TOOL_RESULT, END, etc. |
| SubagentProvider | RFC-1006 §4 | Registration and lazy factory wrapping descriptor + runtime |
| SubagentRoutingPolicy | RFC-1006 §7 | Routing constraints: allow_auto_routing, max_depth, permission_profile |
| Subagents Layer | RFC-1007 §5.3.3 | noesium.subagents; reusable subagent implementations depending on core and toolkits |
| Task | RFC-9000 §6.1 | Primary abstraction in NoeCoder; discrete unit of coding work with lifecycle |
| Task Orchestrator | RFC-9001 §9.2 | Service managing task lifecycle and NoeAgent integration |
| Task Status | RFC-9001 §6.1 | Lifecycle state: created, planning, executing, reflecting, completed, failed |
| Task Step | RFC-9001 §6.1 | Individual execution step within a task with status and result |
| Subagent Call | RFC-1005 §5.1 | Execution modality delegating autonomous reasoning to a cognitive worker |
| Task Agent | RFC-1002 §5.4 | Agent archetype for linear or branching task execution |
| Tool Call | RFC-1005 §5.1 | Execution modality invoking a stateless capability as a procedure |
| Tool Call Action | RFC-1005 §12.1 | NoeAgent action representing a single tool invocation with name and args |
| Tool Context | RFC-2004 §4.2 | Execution context with agent identity, permissions, and trace |
| Tool Executor | RFC-2004 §5 | Event-wrapping execution engine for AtomicTools with permission checking |
| Tool Node | RFC-1005 §12.3 | LangGraph node executing tool calls via ToolExecutor |
| Tool Permission | RFC-2003 §10 | Declared permission requirement: fs:read, shell:execute, net:outbound, etc. |
| Tool Registry | RFC-2004 §8 | Capability-based registry for AtomicTool discovery and lookup |
| Tool Source | RFC-2003 §5 | Classification: builtin, langchain, mcp, or user |
| Toolkits Layer | RFC-1007 §5.3.2 | noesium.toolkits; built-in tool implementations depending on core |
| Toolify | RFC-1001 §12 | Tool system with registry, configuration, and MCP integration |
| Toolkit Registry | RFC-1001 §12 | Auto-discovery registry for built-in and custom toolkits |
| Trace Context | RFC-0002 §6 | Distributed tracing structure: trace_id, span_id, parent_span_id, depth |
| Working Memory | RFC-2001 §5.1 | Session-scoped ephemeral memory tier, dict-backed, no IO |
| WorkingMemoryProvider | RFC-2002 §6.1 | Working memory provider wrapping in-process dict storage |
| Application Layer | RFC-1007 §5.2 | noesium.noeagent; complete agent application depending on all lower layers |
| Artifact | RFC-9001 §6.1 | Generated output from a task (code, document, image) with content or file path |
| CodeChange | RFC-9001 §6.1 | Record of file modification with diff, lines added/removed, and change type |

---

## Usage Guidelines

- **Capitalization**: Use the capitalization shown in the Term column when referring to defined terms
- **First use**: On first use in an RFC, link to this document or the defining RFC
- **Synonyms**: Avoid synonyms; use the canonical term from this table

---

## Related Documents