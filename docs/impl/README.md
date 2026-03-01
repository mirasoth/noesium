# noesium Implementation Guides

This directory contains implementation guides that translate RFC specifications into concrete, project-specific designs.

## Purpose

Implementation guides bridge the gap between abstract specs (RFCs) and actual code. They provide:

- Concrete module/package structure
- Type definitions with full field specifications
- Interface/trait/class definitions
- Implementation details and algorithms
- Error handling strategies
- Testing approaches

## Relationship to Specs

```
RFC Specification (abstract, what)
        |
        v
Implementation Guide (concrete, how)   <-- This directory
        |
        v
Actual Code (executable)
```

Implementation guides **supersede** RFC specs with concrete details but **MUST NOT contradict** them.

## Creating a New Guide

Use the **platonic-impl-guide** skill to create implementation guides:

```
Use platonic-impl-guide to create a guide for RFC-NNNN targeting the <module-name> module.
```

## Guide Template

Use the **platonic-impl-guide** skill which includes its own template for generating implementation guides.

## Current Guides

| Guide | Source RFCs | Description |
|-------|-------------|-------------|
| [core-framework-impl.md](core-framework-impl.md) | RFC-1001 | Core framework modules: event, kernel, projection, capability, memory |
| [agent-framework-impl.md](agent-framework-impl.md) | RFC-1002 | LangGraph-based agent design and base classes |
| [noe-agent-impl.md](noe-agent-impl.md) | RFC-1002, RFC-2001–2004 | NoeAgentNoech assistant with ask/agent modes |
| [goalith-deprecation-impl.md](goalith-deprecation-impl.md) | Assessment | Goalith module deprecation plan and migration |
| [gap-analysis.md](gap-analysis.md) | All RFCs | Gap analysis between specs and current codebase |

## Naming Convention

Name guides descriptively, referencing the feature or RFC:

- `auth-impl.md` - Authentication implementation
- `storage-layer-impl.md` - Storage layer implementation
- `api-contracts-impl.md` - API contracts implementation
