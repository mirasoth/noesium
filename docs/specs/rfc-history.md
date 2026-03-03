# noesium RFC Change History

This document tracks all RFC lifecycle events in chronological order (newest first).

**Last Updated**: 2026-03-03

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

### 2026-03-03

- **Created**: RFC-1004 - Capability Registry Implementation Architecture; Provider-First, Hybrid Event-Sourced design; CapabilityRegistry, provider adapters (Tool, MCP, Skill, Agent, CliAgent), health model, NoeAgent integration
- **Updated**: RFC-0005 - Provider-first, hybrid event-sourced capability registry design; 5-type taxonomy (TOOL, MCP_TOOL, SKILL, AGENT, CLI_AGENT); CapabilityDescriptor and CapabilityProvider protocol; unified CapabilityRegistry; dual health model; hybrid invocation (direct for tools, event-mediated for agents); BaseAgent.declare_capabilities()
- **Reference Updated**: All RFC files moved from `specs/` to `docs/specs/` for better project organization
- **Reference Updated**: rfc-index.md - Updated all RFC paths to reflect new location
- **Reference Updated**: rfc-namings.md - Regenerated with updated RFC paths
- **Reference Updated**: rfc-history.md - Updated Last Updated date

### 2026-03-02

- **Updated**: RFC-0005 - Merged RFC-0005-Patch1 (Persistent External CLI Subagent Daemon Architecture) into RFC-0005 as abstract design; added CapabilityType taxonomy (§4.2), Persistent Subagent Architecture (§10), Subagent Lifecycle Model (§11), Tool vs Subagent comparison (§16); removed NoeAgent-specific references to maintain abstract design
- **Deprecated**: RFC-0005-Patch1 - Merged into RFC-0005, file deleted
- **Reference Updated**: rfc-history.md - Added RFC-0005 merge entry
- **Reference Updated**: rfc-index.md - Updated RFC-0005 last updated date

### 2026-03-01 (Phase 3)

- **Created**: RFC-0006 - Agent Kernel and Sandboxed Subagent Model
- **Created**: RFC-1003 - OpenSandbox-Based Multi-User Agent Isolation Architecture
- **Reference Updated**: rfc-index.md - Registered RFC-0006 and RFC-1003
- **Reference Updated**: rfc-namings.md - Added new terms from RFC-0006 and RFC-1003
- **Reference Updated**: rfc-history.md - Added Phase 3 entries

### 2026-03-01 (Phase 2)

- **Created**: RFC-2001 - Memory Management Architecture
- **Created**: RFC-2002 - Memory Implementation Design
- **Created**: RFC-2003 - Tool System Architecture
- **Created**: RFC-2004 - Tool Implementation Design
- **Reference Updated**: rfc-index.md - Registered RFC-2001 through RFC-2004 under Enhancements
- **Reference Updated**: rfc-namings.md - Added 25+ new terms from RFC-2001 through RFC-2004 and Noe
- **Reference Updated**: rfc-history.md - Added Phase 2 entries

### 2026-03-01

- **Created**: RFC-1001 - Core Framework Implementation Design
- **Created**: RFC-1002 - LangGraph-Based Agent Implementation Design
- **Reference Updated**: rfc-index.md - Added classification scheme and registered all RFCs
- **Reference Updated**: rfc-namings.md - Populated terminology from all active RFCs
- **Updated**: RFC-0001 - Fixed metadata compliance (added Authors, Created, Last Updated, Kind)
- **Updated**: RFC-0002 - Fixed metadata compliance (added Created, Last Updated, Kind)
- **Updated**: RFC-0003 - Fixed metadata compliance (added Created, Last Updated, Kind)
- **Updated**: RFC-0004 - Fixed metadata compliance (replaced Related with Depends on, added dates, Kind)
- **Updated**: RFC-0005 - Fixed metadata compliance (replaced Related with Depends on, added dates, Kind)

### 2025-03-01

- **Created**: RFC-0001 - Event-Sourced Multi-Agent Kernel Architecture
- **Created**: RFC-0002 - Event Schema and Envelope Specification
- **Created**: RFC-0003 - Deterministic Kernel Execution Constraints
- **Created**: RFC-0004 - Projection and Memory Formal Model
- **Created**: RFC-0005 - Capability Registry and Discovery Protocol

---

## Version Update Records

_No versioned RFC updates yet._

---

## Related Documents

- [rfc-standard.md](rfc-standard.md) - RFC process and conventions
- [rfc-index.md](rfc-index.md) - RFC index
- [rfc-namings.md](rfc-namings.md) - Terminology reference
