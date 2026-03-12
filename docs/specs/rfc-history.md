# noesium RFC Change History

This document tracks all RFC lifecycle events in chronological order (newest first).

**Last Updated**: 2026-03-09
**Refinement**: Removed deprecated event-sourcing infrastructure from all specs

---

## Event Types

| Event | Description |
|-------|-------------|
| **Created** | New RFC document created |
| **Updated** | Draft or Review RFC modified |
| **Frozen** | RFC status changed to Frozen |
| **Version Released** | New version of frozen RFC created |
| **Deprecated** | RFC deprecated |
| **Reference Updated** | Supporting doc (index, namings, etc.) updated |

---

## Change History

### 2026-03-09 (Complete Removal)

Complete removal of deprecated event-sourcing infrastructure from specs. Specs now align with current codebase implementation.

**Removed from all specs**:
- EventEnvelope, AgentRef, TraceContext, SignatureBlock, DomainEvent
- EventStore, EnvelopeBridge, ProjectionEngine, BaseProjection
- EventSourcedProvider, DurableMemory, CognitiveProjection
- KernelExecutor with event emission

**Retained Implementation**:
- ProgressEvent for TUI streaming
- CognitiveContext (RFC-1010) for state continuity
- MemuProvider for persistent memory
- Local changelog in CapabilityRegistry

- **Rewritten**: RFC-1001 - Event and Progress Streaming Specification; simplified to document ProgressEvent-based streaming; removed EventEnvelope, AgentRef, TraceContext, SignatureBlock sections entirely; reduced from 465 to ~100 lines
- **Rewritten**: RFC-2001 - Core Framework Implementation Design; removed Event System (EventEnvelope/EventStore/DomainEvent), Projection Layer, Kernel Executor sections; updated to document current package structure; reduced from 934 to ~221 lines
- **Rewritten**: RFC-2102 - Memory Implementation Design; removed EventSourcedProvider section entirely; MemuProvider is now the primary persistent provider; reduced from 549 to ~280 lines
- **Rewritten**: RFC-2103 - Tool Implementation Design; removed DomainEvent-based tool events; simplified ToolExecutor without event emission; reduced from 527 to ~310 lines
- **Reference Updated**: rfc-history.md - Documented complete removal

### 2026-03-08

- **Created**: RFC-1010 - CognitiveContext for Agent State Continuity; defines minimal cognitive state model for context continuity across TUI conversations and subagent interactions; 3-field model (goal, findings, scratchpad) with optional memory integration
- **Reference Updated**: rfc-namings.md - Added CognitiveContext term
- **Reference Updated**: rfc-index.md - Registered RFC-1010 under Core & Agent Architecture (1xxx)
- **Reference Updated**: rfc-history.md - Added RFC-1010 creation entry

### 2026-03-07

- **Updated**: RFC-0001 - Event-Sourced Multi-Agent Kernel Architecture; added implementation status notes; updated Section 3 to prefer mutable state and direct invocation with event-sourced as alternative; rewrote Section 5.2 (Agent Kernel) to document LangGraph-based implementation; rewrote Section 6 (Execution Semantics) to describe direct invocation patterns; added Section 13 (Alternative Architectural Patterns) documenting event-sourced patterns as optional approaches; added Section 14 (Event Infrastructure Overview)
- **Updated**: RFC-1001 - Event Schema and Envelope Specification; added implementation status note; added Section 19 (Implementation and Usage) documenting when to use EventEnvelope with code examples and performance considerations
- **Reference Updated**: rfc-history.md - Added RFC-0001 and RFC-1001 update entries

### 2026-03-07

- **Created**: RFC-1005 - NoeAgent Autonomous Architecture; defines 24/7 autonomous cognitive system with Goal Engine and Cognitive Loop; minimal architecture with five core components; integrates with existing NoeAgent systems
- **Created**: RFC-1006 - Autonomous Goal Engine; defines motivational layer for autonomous architecture; goal model, lifecycle, queue, and scheduling; deterministic goal management without reasoning
- **Created**: RFC-1007 - Event System & Triggers; defines reactive layer for autonomous agent; event model, sources, trigger rules, and Goal Engine integration; minimal deterministic event processing
- **Reference Updated**: rfc-namings.md - Added new terms: Cognitive Loop, Event Queue, Event System, Goal, Goal Engine, Goal Queue, Trigger Rules
- **Reference Updated**: rfc-index.md - Registered RFC-1005, RFC-1006, RFC-1007 under Core & Agent Architecture (1xxx); updated quick links and status lists
- **Reference Updated**: rfc-history.md - Added RFC-1005, RFC-1006, RFC-1007 creation entries

### 2026-03-07

- **Deleted**: RFC-0003 - Deterministic Kernel Execution Constraints; design moved to RFC-1001 implementation layer; kernel executor concept retained but not as separate architectural spec
- **Reference Updated**: All RFCs updated to remove RFC-0003 from dependencies and references
- **Reference Updated**: rfc-index.md - Removed RFC-0003 from Global Architecture section
- **Reference Updated**: rfc-namings.md - Removed terms: Checkpoint, Deterministic Kernel, State Graph
- **Reference Updated**: rfc-history.md - Added deletion entry
- **Reference Updated**: AGENTS.md, all implementation docs - Updated RFC references

### 2026-03-05

- **Updated**: RFC-1004 - Logic consistency (Option A): renamed "Subagent" to **Effect Executor** for sandboxed tool runner; title to "Agent Kernel and Sandboxed Effect Executor Model"; added terminology note distinguishing Effect Executor from Subagent (RFC-1008/1009)
- **Updated**: RFC-1003 - Replaced "subagent" with "effect executor" for sandboxed execution (alignment with RFC-1004)
- **Reference Updated**: rfc-namings.md - Subagent now cites RFC-1008 §5.1 (cognitive agent); added Effect Executor (RFC-1004 §5.2); Agent Kernel Pod now "effect executor dispatch"
- **Reference Updated**: rfc-index.md - RFC-1004 title and Last Updated; logic-consistency-review.md resolution checklist
- **Created**: RFC-1007 - Noesium Framework Layered Impl Architecture; four-layer architecture (core, toolkits, subagents, noeagent); dependency direction and import restrictions; FrameworkConfig; public API surface per layer
- **Updated**: RFC-1006 - Merged RFC-9004 content (SubagentContext, HITL Protocol, Dynamic Discovery); added Section 5.6 SubagentContext for memory/state sharing; added Section 5.7 HITL Protocol for human-in-the-loop pause/resume; added Section 6.3 Dynamic Discovery via entry points; updated Section 5.4 with HITL event types; updated Section 5.5 with resume() method; implemented core subagent module in noesium/core/agent/subagent/
- **Deleted**: RFC-9004 - Content merged into RFC-1006, file deleted
- **Created**: RFC-1006 - Extensible Subagent Interface for Core Agent Framework (formerly RFC-9003)
- **Reference Updated**: rfc-index.md - Registered RFC-1006 and RFC-1007 under Core Framework (1xxx), deleted RFC-9003/RFC-9004, updated quick links

### 2026-03-03

- **Created**: RFC-1005 - Tool Call vs Subagent Call Distinction; ontological distinction between tools and subagents; control flow semantics; state and memory model; temporal scope; failure semantics; decision heuristics; implementation mapping in NoeAgent LangGraph workflow; anti-patterns; cost and performance considerations
- **Created**: RFC-1004 - Capability Registry Implementation Architecture; Provider-First, Hybrid Event-Sourced design; CapabilityRegistry, provider adapters (Tool, MCP, Skill, Agent, CliAgent), health model, NoeAgent integration
- **Updated**: RFC-1003 - Provider-first, hybrid event-sourced capability registry design; 5-type taxonomy (TOOL, MCP_TOOL, SKILL, AGENT, CLI_AGENT); CapabilityDescriptor and CapabilityProvider protocol; unified CapabilityRegistry; dual health model; hybrid invocation (direct for tools, event-mediated for agents); BaseAgent.declare_capabilities()
- **Reference Updated**: All RFC files moved from `specs/` to `docs/specs/` for better project organization
- **Reference Updated**: rfc-index.md - Updated all RFC paths to reflect new location
- **Reference Updated**: rfc-namings.md - Regenerated with updated RFC paths
- **Reference Updated**: rfc-history.md - Updated Last Updated date

### 2026-03-02

- **Updated**: RFC-1003 - Merged RFC-1003-Patch1 (Persistent External CLI Subagent Daemon Architecture) into RFC-1003 as abstract design; added CapabilityType taxonomy (§4.2), Persistent Subagent Architecture (§10), Subagent Lifecycle Model (§11), Tool vs Subagent comparison (§16); removed NoeAgent-specific references to maintain abstract design
- **Deprecated**: RFC-1003-Patch1 - Merged into RFC-1003, file deleted
- **Reference Updated**: rfc-history.md - Added RFC-1003 merge entry
- **Reference Updated**: rfc-index.md - Updated RFC-1003 last updated date

### 2026-03-01 (Phase 3)

- **Created**: RFC-1004 - Agent Kernel and Sandboxed Subagent Model
- **Created**: RFC-2101 - OpenSandbox-Based Multi-User Agent Isolation Architecture
- **Reference Updated**: rfc-index.md - Registered RFC-1004 and RFC-2101
- **Reference Updated**: rfc-namings.md - Added new terms from RFC-1004 and RFC-2101
- **Reference Updated**: rfc-history.md - Added Phase 3 entries

### 2026-03-01 (Phase 2)

- **Created**: RFC-1101 - Memory Management Architecture
- **Created**: RFC-2102 - Memory Implementation Design
- **Created**: RFC-1201 - Tool System Architecture
- **Created**: RFC-2103 - Tool Implementation Design
- **Reference Updated**: rfc-index.md - Registered RFC-2001 through RFC-2004 under Enhancements
- **Reference Updated**: rfc-namings.md - Added 25+ new terms from RFC-2001 through RFC-2004 and Noe
- **Reference Updated**: rfc-history.md - Added Phase 2 entries

### 2026-03-01

- **Created**: RFC-2001 - Core Framework Implementation Design
- **Created**: RFC-2002 - LangGraph-Based Agent Implementation Design
- **Reference Updated**: rfc-index.md - Added classification scheme and registered all RFCs
- **Reference Updated**: rfc-namings.md - Populated terminology from all active RFCs
- **Updated**: RFC-0001 - Fixed metadata compliance (added Authors, Created, Last Updated, Kind)
- **Updated**: RFC-1001 - Fixed metadata compliance (added Created, Last Updated, Kind)
- **Updated**: RFC-1002 - Fixed metadata compliance (replaced Related with Depends on, added dates, Kind)
- **Updated**: RFC-1003 - Fixed metadata compliance (replaced Related with Depends on, added dates, Kind)

### 2025-03-01

- **Created**: RFC-0001 - Event-Sourced Multi-Agent Kernel Architecture
- **Created**: RFC-1001 - Event Schema and Envelope Specification
- **Created**: RFC-1002 - Projection and Memory Formal Model
- **Created**: RFC-1003 - Capability Registry and Discovery Protocol

---

## Version Update Records

_No versioned RFC updates yet._

---

## Related Documents

- [rfc-standard.md](rfc-standard.md) - RFC process and conventions
- [rfc-index.md](rfc-index.md) - RFC index
- [rfc-namings.md](rfc-namings.md) - Terminology reference
