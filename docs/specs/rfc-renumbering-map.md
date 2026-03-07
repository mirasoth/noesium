# RFC Renumbering Map

**Created**: 2026-03-07
**Purpose**: Document the renumbering of RFCs from the old 4-category classification to the new Kind-based classification with sub-ranges.

---

## Classification Change Summary

### Old Classification
| Range | Category |
|-------|----------|
| RFC-0xxx | Global Architecture |
| RFC-1xxx | Core Framework |
| RFC-2xxx | Enhancements |
| RFC-9xxx | Experimental |

### New Classification
| Range | Category | Sub-ranges |
|-------|----------|------------|
| RFC-0xxx | Conceptual Design | — |
| RFC-1xxx | Architecture Design | 1000-1099: Core & Agent<br>1100-1199: Memory<br>1200-1299: Tools & Capabilities<br>1300-1399: Security & Isolation |
| RFC-2xxx | Implementation Interface Design | 2000-2099: Core Implementation<br>2100-2199: Infrastructure Implementation |
| RFC-9xxx | Applications & Research | 9000-9099: Research Projects<br>9100-9199: Application Designs |

---

## Renumbering Mapping Table

### RFC-0xxx: Conceptual Design

| Old RFC | Title | Old Kind | New RFC | New Sub-Range | Status |
|---------|-------|----------|---------|---------------|--------|
| RFC-0001 | Event-Sourced Multi-Agent Kernel Architecture | Conceptual Design | **RFC-0001** | — | ✓ No change |

### RFC-1xxx: Architecture Design

#### Sub-range 1000-1099: Core & Agent Architecture

| Old RFC | Title | Old Kind | New RFC | Notes |
|---------|-------|----------|---------|-------|
| RFC-0002 | Event Schema and Envelope Specification | Architecture Design | **RFC-1001** | Move from 0xxx |
| RFC-0004 | Projection and Memory Formal Model | Architecture Design | **RFC-1002** | Move from 0xxx |
| RFC-0005 | Capability Registry and Discovery Protocol | Architecture Design | **RFC-1003** | Move from 0xxx |
| RFC-0006 | Agent Kernel and Sandboxed Effect Executor Model | Architecture Design | **RFC-1004** | Move from 0xxx |
| RFC-0007 | NoeAgent Autonomous Architecture | Architecture Design | **RFC-1005** | Move from 0xxx |
| RFC-0008 | Autonomous Goal Engine | Architecture Design | **RFC-1006** | Move from 0xxx |
| RFC-0009 | Event System & Triggers | Architecture Design | **RFC-1007** | Move from 0xxx |
| RFC-1006 | Extensible Subagent Interface for Core Agent Framework | Architecture Design | **RFC-1008** | Renumber from 1006 |
| RFC-1007 | Noesium Framework Layered Impl Architecture | Architecture Design | **RFC-1009** | Renumber from 1007 |

#### Sub-range 1100-1199: Memory Architecture

| Old RFC | Title | Old Kind | New RFC | Notes |
|---------|-------|----------|---------|-------|
| RFC-2001 | Memory Management Architecture | Architecture Design | **RFC-1101** | Move from 2xxx |

#### Sub-range 1200-1299: Tool & Capability Architecture

| Old RFC | Title | Old Kind | New RFC | Notes |
|---------|-------|----------|---------|-------|
| RFC-2003 | Tool System Architecture | Architecture Design | **RFC-1201** | Move from 2xxx |

#### Sub-range 1300-1399: Security & Isolation Architecture

| Old RFC | Title | Old Kind | New RFC | Notes |
|---------|-------|----------|---------|-------|
| — | — | — | — | *(Reserved for future RFCs)* |

### RFC-2xxx: Implementation Interface Design

#### Sub-range 2000-2099: Core Implementation

| Old RFC | Title | Old Kind | New RFC | Notes |
|---------|-------|----------|---------|-------|
| RFC-1001 | Core Framework Implementation Design | Implementation Interface Design | **RFC-2001** | Move from 1xxx |
| RFC-1002 | LangGraph-Based Agent Implementation Design | Implementation Interface Design | **RFC-2002** | Move from 1xxx |
| RFC-1004 | Capability Registry Implementation Architecture | Implementation Interface Design | **RFC-2003** | Move from 1xxx |
| RFC-1005 | Tool Call vs Subagent Call Distinction | Implementation Interface Design | **RFC-2004** | Move from 1xxx |

#### Sub-range 2100-2199: Infrastructure Implementation

| Old RFC | Title | Old Kind | New RFC | Notes |
|---------|-------|----------|---------|-------|
| RFC-1003 | OpenSandbox-Based Multi-User Agent Isolation Architecture | Implementation Interface Design | **RFC-2101** | Move from 1xxx |
| RFC-2002 | Memory Implementation Design | Implementation Interface Design | **RFC-2102** | Move from 2xxx |
| RFC-2004 | Tool Implementation Design | Implementation Interface Design | **RFC-2103** | Move from 2xxx |

### RFC-9xxx: Applications & Research

#### Sub-range 9000-9099: Research Projects

| Old RFC | Title | Old Kind | New RFC | Notes |
|---------|-------|----------|---------|-------|
| RFC-9000 | Voyager Design Philosophy and Principles | Conceptual Design | **RFC-9000** | ✓ No change |
| RFC-9001 | Voyager Architecture Design | Architecture Design | **RFC-9001** | ✓ No change |

---

## Cross-Reference Dependencies

### Dependencies That Need Updating

When renumbering RFCs, the following cross-references must be updated in dependent RFCs:

#### RFC-0002 → RFC-1001 (Event Schema)
**Referenced by**:
- RFC-2001 (→ RFC-1101) - `Depends on: RFC-0002`
- RFC-0004 (→ RFC-1002) - Internal references
- Multiple implementation RFCs

#### RFC-0004 → RFC-1002 (Projection and Memory)
**Referenced by**:
- RFC-0007 (→ RFC-1005) - `Depends on: RFC-0004`
- RFC-2001 (→ RFC-1101) - `Depends on: RFC-0004`
- RFC-2002 (→ RFC-2102) - References

#### RFC-0005 → RFC-1003 (Capability Registry)
**Referenced by**:
- RFC-0006 (→ RFC-1004) - `Depends on: RFC-0005`
- RFC-0007 (→ RFC-1005) - `Depends on: RFC-0005`
- RFC-1005 (→ RFC-2004) - `Depends on: RFC-0005`
- RFC-1004 (→ RFC-2003) - Implementation references

#### RFC-0006 → RFC-1004 (Agent Kernel)
**Referenced by**:
- RFC-1003 (→ RFC-2101) - `Depends on: RFC-0006`

#### RFC-1001 → RFC-2001 (Core Framework Implementation)
**Referenced by**:
- RFC-1005 (→ RFC-2004) - `Depends on: RFC-1001`
- RFC-9000 (no change) - `Depends on: RFC-1001`

#### RFC-1002 → RFC-2002 (LangGraph Implementation)
**Referenced by**:
- RFC-1005 (→ RFC-2004) - `Depends on: RFC-1002`
- RFC-9000 (no change) - `Depends on: RFC-1002`

#### RFC-1004 → RFC-2003 (Capability Registry Implementation)
**Referenced by**:
- RFC-9000 (no change) - `Depends on: RFC-1004`

#### RFC-1006 → RFC-1008 (Subagent Interface)
**Referenced by**: (Check for dependencies)

#### RFC-1007 → RFC-1009 (Layered Architecture)
**Referenced by**: (Check for dependencies)

#### RFC-2001 → RFC-1101 (Memory Architecture)
**Referenced by**:
- RFC-2002 (→ RFC-2102) - References architecture

#### RFC-2003 → RFC-1201 (Tool System Architecture)
**Referenced by**:
- RFC-1005 (→ RFC-2004) - `Depends on: RFC-2003`
- RFC-2004 (→ RFC-2103) - References architecture

#### RFC-2004 → RFC-2103 (Tool Implementation)
**Referenced by**:
- RFC-1005 (→ RFC-2004) - `Depends on: RFC-2004`

---

## Edge Cases and Notes

### Kind Preservation
All RFCs retain their original `Kind` metadata value. The classification is based on Kind, so this provides consistency.

### Status Preservation
All RFCs retain their `Draft` status. Only the RFC number and references change.

### Date Updates
All RFCs get `Last Updated: 2026-03-07` to reflect the renumbering.

### Sequential Numbering Within Sub-ranges
Within each sub-range, numbers are assigned sequentially:
- Core & Agent: 1001-1009 (no gaps)
- Memory: 1101 (next would be 1102)
- Tools: 1201 (next would be 1202)
- Core Impl: 2001-2004 (no gaps)
- Infrastructure Impl: 2101-2103 (no gaps)

### Special Cases
1. **RFC-0001**: Remains RFC-0001 as the sole conceptual design RFC
2. **RFC-9000, RFC-9001**: Remain unchanged in the 9xxx range
3. **RFC-1003**: Moved to 2xxx range (2101) because it's implementation interface design for infrastructure (OpenSandbox)

---

## Files to Update

### RFC Files (20 files)
All RFC files must be renamed:
- 19 files renamed to new numbers
- 1 file (RFC-0001) unchanged
- 2 files (RFC-9000, RFC-9001) unchanged

### Documentation Files (3 files)
1. `rfc-standard.md` - Update classification scheme
2. `rfc-index.md` - Update all RFC entries and references
3. `rfc-history.md` - Add renumbering event

### Supporting Files (optional)
- Any scripts that reference RFC numbers
- Any external documentation referencing RFC numbers

---

## Execution Checklist

- [ ] Create renumbering map (this document)
- [ ] Update rfc-standard.md with new classification
- [ ] Rename all RFC files
- [ ] Update cross-references in each RFC
- [ ] Update rfc-index.md
- [ ] Validate all changes
- [ ] Update rfc-history.md with renumbering event

---

## Statistics

- **Total RFCs**: 21
- **RFCs renumbered**: 18
- **RFCs unchanged**: 3
- **Cross-references to update**: ~15-20
- **Files renamed**: 18

---

**Generated**: 2026-03-07
**Classification**: Kind-Based with Sub-ranges