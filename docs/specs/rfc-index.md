# noesium RFC Index

Master index of all RFC specifications.

**Last Updated**: 2026-03-07

---

## Classification Scheme

| Range | Category | Sub-ranges |
|-------|----------|------------|
| **RFC-0xxx** | Conceptual Design | — |
| **RFC-1xxx** | Architecture Design | 1000-1099: Core & Agent<br>1100-1199: Memory<br>1200-1299: Tools & Capabilities<br>1300-1399: Security & Isolation |
| **RFC-2xxx** | Implementation Interface Design | 2000-2099: Core Implementation<br>2100-2199: Infrastructure Implementation |
| **RFC-9xxx** | Applications & Research | 9000-9099: Research Projects<br>9100-9199: Application Designs |

---

## Active RFCs

### RFC-0xxx: Conceptual Design

| RFC | Title | Kind | Status | Created | Last Updated | Version |
|-----|-------|------|--------|---------|--------------|---------|
| [RFC-0001](RFC-0001.md) | Event-Sourced Multi-Agent Kernel Architecture | Conceptual Design | Draft | 2025-03-01 | 2026-03-07 | 001 |

### RFC-1xxx: Architecture Design

#### Sub-range 1000-1099: Core & Agent Architecture

| RFC | Title | Kind | Status | Created | Last Updated | Version |
|-----|-------|------|--------|---------|--------------|---------|
| [RFC-1001](RFC-1001.md) | Event Schema and Envelope Specification | Architecture Design | Draft | 2025-03-01 | 2026-03-07 | 001 |
| [RFC-1002](RFC-1002.md) | Projection and Memory Formal Model | Architecture Design | Draft | 2025-03-01 | 2026-03-07 | 001 |
| [RFC-1003](RFC-1003.md) | Capability Registry and Discovery Protocol | Architecture Design | Draft | 2025-03-01 | 2026-03-07 | 001 |
| [RFC-1004](RFC-1004.md) | Agent Kernel and Sandboxed Effect Executor Model | Architecture Design | Draft | 2026-03-01 | 2026-03-07 | 001 |
| [RFC-1005](RFC-1005.md) | NoeAgent Autonomous Architecture | Architecture Design | Draft | 2026-03-07 | 2026-03-07 | 001 |
| [RFC-1006](RFC-1006.md) | Autonomous Goal Engine | Architecture Design | Draft | 2026-03-07 | 2026-03-07 | 001 |
| [RFC-1007](RFC-1007.md) | Event System & Triggers | Architecture Design | Draft | 2026-03-07 | 2026-03-07 | 001 |
| [RFC-1008](RFC-1008.md) | Extensible Subagent Interface for Core Agent Framework | Architecture Design | Draft | 2026-03-05 | 2026-03-07 | 001 |
| [RFC-1009](RFC-1009.md) | Noesium Framework Layered Impl Architecture | Architecture Design | Draft | 2026-03-05 | 2026-03-07 | 001 |

#### Sub-range 1100-1199: Memory Architecture

| RFC | Title | Kind | Status | Created | Last Updated | Version |
|-----|-------|------|--------|---------|--------------|---------|
| [RFC-1101](RFC-1101.md) | Memory Management Architecture | Architecture Design | Draft | 2026-03-01 | 2026-03-07 | 001 |

#### Sub-range 1200-1299: Tool & Capability Architecture

| RFC | Title | Kind | Status | Created | Last Updated | Version |
|-----|-------|------|--------|---------|--------------|---------|
| [RFC-1201](RFC-1201.md) | Tool System Architecture | Architecture Design | Draft | 2026-03-01 | 2026-03-07 | 001 |

### RFC-2xxx: Implementation Interface Design

#### Sub-range 2000-2099: Core Implementation

| RFC | Title | Kind | Status | Created | Last Updated | Version |
|-----|-------|------|--------|---------|--------------|---------|
| [RFC-2001](RFC-2001.md) | Core Framework Implementation Design | Implementation Interface Design | Draft | 2026-03-01 | 2026-03-07 | 001 |
| [RFC-2002](RFC-2002.md) | LangGraph-Based Agent Implementation Design | Implementation Interface Design | Draft | 2026-03-01 | 2026-03-07 | 001 |
| [RFC-2003](RFC-2003.md) | Capability Registry Implementation Architecture | Implementation Interface Design | Draft | 2026-03-03 | 2026-03-07 | 001 |
| [RFC-2004](RFC-2004.md) | Tool Call vs Subagent Call Distinction | Implementation Interface Design | Draft | 2026-03-03 | 2026-03-07 | 001 |

#### Sub-range 2100-2199: Infrastructure Implementation

| RFC | Title | Kind | Status | Created | Last Updated | Version |
|-----|-------|------|--------|---------|--------------|---------|
| [RFC-2101](RFC-2101.md) | OpenSandbox-Based Multi-User Agent Isolation Architecture | Implementation Interface Design | Draft | 2026-03-01 | 2026-03-07 | 001 |
| [RFC-2102](RFC-2102.md) | Memory Implementation Design | Implementation Interface Design | Draft | 2026-03-01 | 2026-03-07 | 001 |
| [RFC-2103](RFC-2103.md) | Tool Implementation Design | Implementation Interface Design | Draft | 2026-03-01 | 2026-03-07 | 001 |

### RFC-9xxx: Applications & Research

#### Sub-range 9000-9099: Research Projects

| RFC | Title | Kind | Status | Created | Last Updated | Version |
|-----|-------|------|--------|---------|--------------|---------|
| [RFC-9000](RFC-9000.md) | Voyager Design Philosophy and Principles | Conceptual Design | Draft | 2026-03-04 | 2026-03-07 | 001 |
| [RFC-9001](RFC-9001.md) | Voyager Architecture Design | Architecture Design | Draft | 2026-03-04 | 2026-03-07 | 001 |

---

## Supporting Documents

| Document | Purpose |
|----------|---------|
| [rfc-standard.md](rfc-standard.md) | RFC process and conventions |
| [rfc-namings.md](rfc-namings.md) | Terminology reference |
| [rfc-history.md](rfc-history.md) | Change history |
| [rfc-index.md](rfc-index.md) | This document |
| [rfc-renumbering-map.md](rfc-renumbering-map.md) | Renumbering mapping from old to new numbering |
| [noesium-deepagents-openagents.md](noesium-deepagents-openagents.md) | Comparative analysis |

---

## Status Legend

| Status | Meaning |
|--------|--------|
| **Draft** | Work in progress, subject to change |
| **Review** | Complete, ready for review |
| **Frozen** | Immutable production reference |
| **Superseded** | Replaced by another RFC |
| **Deprecated** | No longer active |

---

## Quick Links

### By Kind

- **Conceptual Design**: [RFC-0001](RFC-0001.md), [RFC-9000](RFC-9000.md)
- **Architecture Design**: [RFC-1001](RFC-1001.md), [RFC-1002](RFC-1002.md), [RFC-1003](RFC-1003.md), [RFC-1004](RFC-1004.md), [RFC-1005](RFC-1005.md), [RFC-1006](RFC-1006.md), [RFC-1007](RFC-1007.md), [RFC-1008](RFC-1008.md), [RFC-1009](RFC-1009.md), [RFC-1101](RFC-1101.md), [RFC-1201](RFC-1201.md), [RFC-9001](RFC-9001.md)
- **Implementation Interface Design**: [RFC-2001](RFC-2001.md), [RFC-2002](RFC-2002.md), [RFC-2003](RFC-2003.md), [RFC-2004](RFC-2004.md), [RFC-2101](RFC-2101.md), [RFC-2102](RFC-2102.md), [RFC-2103](RFC-2103.md)

### By Status

- **Draft**: RFC-0001, RFC-1001, RFC-1002, RFC-1003, RFC-1004, RFC-1005, RFC-1006, RFC-1007, RFC-1008, RFC-1009, RFC-1101, RFC-1201, RFC-2001, RFC-2002, RFC-2003, RFC-2004, RFC-2101, RFC-2102, RFC-2103, RFC-9000, RFC-9001
- **Review**: _None yet_
- **Frozen**: _None yet_

### By Category

- **Conceptual Design (0xxx)**: [RFC-0001](RFC-0001.md)
- **Architecture Design (1xxx)**: [RFC-1001](RFC-1001.md), [RFC-1002](RFC-1002.md), [RFC-1003](RFC-1003.md), [RFC-1004](RFC-1004.md), [RFC-1005](RFC-1005.md), [RFC-1006](RFC-1006.md), [RFC-1007](RFC-1007.md), [RFC-1008](RFC-1008.md), [RFC-1009](RFC-1009.md), [RFC-1101](RFC-1101.md), [RFC-1201](RFC-1201.md), [RFC-9001](RFC-9001.md)
- **Implementation Interface Design (2xxx)**: [RFC-2001](RFC-2001.md), [RFC-2002](RFC-2002.md), [RFC-2003](RFC-2003.md), [RFC-2004](RFC-2004.md), [RFC-2101](RFC-2101.md), [RFC-2102](RFC-2102.md), [RFC-2103](RFC-2103.md)
- **Applications & Research (9xxx)**: [RFC-9000](RFC-9000.md), [RFC-9001](RFC-9001.md)

---

## Related Documents

- [rfc-standard.md](rfc-standard.md) - RFC process and conventions
- [rfc-history.md](rfc-history.md) - Change history
- [rfc-namings.md](rfc-namings.md) - Terminology reference
- [rfc-renumbering-map.md](rfc-renumbering-map.md) - Renumbering mapping document