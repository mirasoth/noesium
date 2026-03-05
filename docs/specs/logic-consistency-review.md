# Logic Consistency Review: docs/specs

**Date**: 2026-03-05  
**Scope**: Cross-spec logic consistency (terminology, ontology, dependency alignment, conflicting constraints)  
**Method**: Platonic-specs–style validation + semantic analysis across RFCs  

---

## 1. Summary

| Severity | Count | Description |
|----------|--------|-------------|
| **Error** | 0 | *(Resolved 2026-03-05: Option A applied)* |
| **Warnings** | 0 | — |
| **Consistent** | — | Dependency chain, capability taxonomy, memory hierarchy, layering |

**Resolution (2026-03-05)**: The term **Subagent** was used for two concepts. **Option A** was applied: RFC-0006's sandboxed tool runner was renamed to **Effect Executor**; **Subagent** is now reserved for the cognitive-agent meaning (RFC-1005, RFC-1006). See §2.3 and rfc-namings.md.

---

## 2. Error: Subagent — Two Distinct Concepts

### 2.1 Evidence

**RFC-0006 (Agent Kernel and Sandboxed Subagent Model)** defines:

- **Subagent** = *"An isolated execution unit created when the Kernel requires an external effect."*
- Runs inside **sandbox runtime**
- Has restricted **capability scope**, time/resource limits
- Returns structured **EffectResult**
- **Ephemeral**, destroyed after execution
- Used for: executing a single **ToolCall** (e.g. `fs.read`, shell, Python) and returning an effect result

So in RFC-0006, "Subagent" is the **sandboxed executor of one tool/effect** (effect node).

**RFC-1005 (Tool Call vs Subagent Call Distinction)** and **RFC-1006 (Extensible Subagent Interface)** define:

- **Subagent (call)** = execution modality that *"extends NoeAgent's cognition"*
- **Stateful**, session-scoped (AGENT, CLI_AGENT in RFC-0005)
- Delegated **reasoning entity** (e.g. Tacitus, BrowserUse, in-process child NoeAgent)
- Invoked via **SubagentAction**; event-mediated; has **SubagentDescriptor**, **BaseSubagentRuntime**, **SubagentManager**, etc.

So in RFC-1005/1006 (and RFC-0005 §4.2, RFC-1004, RFC-1007), "subagent" is the **delegated cognitive agent**, not the sandboxed tool runner.

### 2.2 Why This Is a Logic Consistency Issue

- **Same term, two concepts**  
  - Concept A (RFC-0006): sandboxed **tool/effect executor** (one ToolCall → one EffectResult).  
  - Concept B (RFC-1005/1006): **cognitive agent** (orchestrator delegates to Tacitus, BrowserUse, CLI agent, etc.).

- **Different lifecycle and scope**  
  - RFC-0006: ephemeral, per-tool-call.  
  - RFC-1005/1006: session-scoped, stateful, multi-step.

- **Different capability types**  
  - RFC-0006's "Subagent" executes **TOOL** (and similar) effects.  
  - RFC-1005/1006's "subagent" is **AGENT** or **CLI_AGENT** in RFC-0005's taxonomy.

- **rfc-namings.md** currently has a single entry:  
  - **Subagent** | RFC-0006 §5.2 | "Isolated execution unit running inside sandbox runtime for **external tool execution**"  
  That matches only RFC-0006's meaning and does not cover the cognitive-agent meaning used in RFC-1005/1006/1007.

So specs are **logically consistent** in behavior (tool execution vs agent delegation are distinct flows), but **terminology is inconsistent**: one name is used for two different concepts, which can cause confusion and wrong assumptions when reading multiple RFCs.

### 2.3 Recommended Resolution

**Option A (recommended): Rename RFC-0006's concept**

- In **RFC-0006** (and **RFC-1003** where it "implements the sandboxed subagent architecture"):
  - Replace the term **Subagent** for the sandboxed tool executor with a distinct term, e.g.:
    - **Effect Executor**, or
    - **Sandboxed Executor**, or
    - **Tool Executor Pod**
  - Reserve **Subagent** for the cognitive-agent meaning (RFC-0005 AGENT/CLI_AGENT, RFC-1005, RFC-1006, RFC-1007).
- Update **rfc-namings.md**:
  - Keep **Subagent** for the cognitive-agent meaning (and cite RFC-1005 or RFC-1006 as primary).
  - Add a new entry for the RFC-0006 concept (e.g. **Effect Executor** or **Sandboxed Executor**) with source RFC-0006 §5.2.
- In **RFC-0006**, add a short "Terminology" or "Relationship" note: e.g. "The sandboxed unit in this RFC (Effect Executor) is distinct from the Subagent in RFC-1005/1006 (delegated cognitive agent)."

**Option B: Disambiguate in place**

- Keep both uses of "Subagent" but disambiguate explicitly:
  - In **RFC-0006**: add a note that "Subagent" here means "sandboxed **effect** executor" and is distinct from the "**cognitive** subagent" in RFC-1005/1006.
  - In **RFC-1005** and **RFC-1006**: add a note that "Subagent" here means "delegated cognitive agent" and is distinct from the "sandboxed effect executor" in RFC-0006.
  - In **rfc-namings.md**: add two entries, e.g. **Subagent (effect executor)** (RFC-0006) and **Subagent (cognitive)** (RFC-1005/1006), with one sentence each to avoid ambiguity.

Option A gives one term per concept and is clearer long-term.

---

## 3. Areas Checked and Found Consistent

### 3.1 Dependency Chain

- No circular dependencies.
- All "Depends on" targets exist and match the intended abstraction level (e.g. RFC-1006 depends on RFC-0005, RFC-1004, RFC-1005, RFC-2004; RFC-1004 implements RFC-0005).

### 3.2 Capability Taxonomy (RFC-0005 ↔ RFC-1004 ↔ RFC-1005 ↔ RFC-1006)

- **RFC-0005**: Defines `CapabilityType`: TOOL, MCP_TOOL, SKILL, AGENT, CLI_AGENT; stateful = AGENT | CLI_AGENT; "tool extends capability, subagent extends cognition."
- **RFC-1004**: Implements same types (e.g. AGENT = "In-process subagent", CLI_AGENT = "External CLI subagent"); `subagent_node` and tool path align with RFC-0005.
- **RFC-1005**: Tool Call vs Subagent Call distinction matches RFC-0005's taxonomy and invocation (direct vs event-mediated).
- **RFC-1006**: Subagents as first-class capabilities (`CapabilityType.AGENT`), SubagentProvider/CapabilityRegistry integration; no conflict with RFC-0005 or RFC-1004.

Logic is consistent: one taxonomy, one registry, and tool vs (cognitive) subagent behavior aligned across these specs.

### 3.3 Memory Hierarchy (RFC-0004 ↔ RFC-2001 ↔ RFC-2002)

- **RFC-0004**: Ephemeral, Durable, Semantic; projections; execution vs cognitive memory.
- **RFC-2001**: Working = session-scoped/ephemeral, Persistent = durable, Indexed = semantic; unifies event-driven stack with MemU; recall protocol.
- **RFC-2002**: Implements providers (WorkingMemoryProvider, EventSourcedProvider, etc.) per RFC-2001.

Tier names and roles align; no conflicting invariants.

### 3.4 Layering (RFC-1007)

- **RFC-1007**: core ← toolkits ← subagents ← noeagent; lower layers MUST NOT import from higher.
- **RFC-1006**: Subagent abstractions live under `noesium/core/agent/subagent/` (core).
- **RFC-1007**: "Subagents" layer = `noesium.subagents` (Tacitus, Askura, BU) = implementations of the cognitive subagent concept.

No conflict: core defines the interface; subagents layer provides implementations that depend on core and toolkits.

### 3.5 Event and Envelope (RFC-0002)

- RFC-0005, RFC-1001, RFC-1002, and others reference RFC-0002 for event envelope and schema; no contradictory event models found.

---

## 4. Recommendations

1. **Resolve Subagent naming** using Option A (rename RFC-0006's concept) or Option B (explicit disambiguation) and update rfc-namings.md accordingly.
2. **Cross-link in RFCs**: In RFC-0006 (and RFC-1003), add one sentence linking to RFC-1005/1006 so readers see the distinction between "sandboxed effect executor" and "cognitive subagent."
3. **Re-run** this logic-consistency review after any change to capability types, subagent model, or memory hierarchy to catch new conflicts early.

---

## 5. Verification Checklist

- [x] Dependency graph acyclic and references valid.
- [x] Capability types and invocation (tool vs agent) consistent across RFC-0005, RFC-1004, RFC-1005, RFC-1006.
- [x] Memory tiers and roles consistent across RFC-0004, RFC-2001, RFC-2002.
- [x] Layering (RFC-1007) consistent with core vs subagents layer and RFC-1006.
- [x] **Subagent**: Resolved via Option A — RFC-0006 concept renamed to **Effect Executor**; rfc-namings and RFC-0006/RFC-1003 updated.
