# Goalith Module Deprecation & Migration Architecture

> Implementation guide for deprecating the Goalith module and migrating useful functionality into the Noesium core architecture.
>
> **Module**: `noesium/core/goalith/` (to be deprecated)
> **Source**: Assessment against [RFC-1001](../../specs/RFC-1001.md), [RFC-1002](../../specs/RFC-1002.md), [RFC-2003](../../specs/RFC-2003.md)
> **Related RFCs**: [RFC-0003](../../specs/RFC-0003.md), [RFC-0004](../../specs/RFC-0004.md), [RFC-0005](../../specs/RFC-0005.md)
> **Language**: Python 3.11+

---

## 1. Overview

### 1.1 Assessment Summary

The Goalith module (`noesium/core/goalith/`) was designed as a standalone DAG-based goal management system. After thorough assessment against the current Noesium architecture, **the module is recommended for deprecation** with one capability extracted: goal decomposition via LLM.

### 1.2 Key Findings

| Aspect | Status | Detail |
|--------|--------|--------|
| **Usage in codebase** | **None** | No imports from agents, toolkits, or other core modules |
| **GoalithService** | **Stub** | `create_goal()` has no implementation |
| **ConflictDetector** | **Stub** | `detect_conflicts()` returns `[]` (TODO) |
| **Replanner** | **Stub** | `replan()` raises `NotImplementedError` |
| **Example code** | **Broken** | `goalith_decomposer.py` references non-existent APIs and exports |
| **LLMDecomposer** | **Buggy** | References `decomposition_strategy` field that doesn't exist |
| **Tags type mismatch** | **Bug** | `GoalNode.tags: List[str]` but code passes `set(...)` |

### 1.3 Overlap with New Architecture

| Goalith Feature | New Architecture Equivalent |
|-----------------|---------------------------|
| GoalGraph (NetworkX DAG) | LangGraph StateGraph (RFC-0003, RFC-1002) |
| GoalNode lifecycle (PENDING→COMPLETED) | ExecutionProjection task_states (RFC-1001) |
| GoalGraph persistence (JSON) | EventStore + projections (RFC-1001) |
| Dependency tracking | LangGraph edges + conditional routing |
| Conflict detection (stub) | Event-based consistency via projections |
| Replanning (stub) | Agent reflection nodes in LangGraph (RFC-1002) |
| **Goal decomposition (LLM)** | **No direct equivalent -- extract** |

### 1.4 Recommendation

**Deprecate the entire `noesium/core/goalith/` module.** Extract the LLM-based goal decomposition concept into `TaskPlanner` within Noet (see `docs/impl/noe-agent-impl.md` §5.2).

---

## 2. What to Extract

### 2.1 Goal Decomposition → TaskPlanner

The only Goalith capability not covered by the new architecture is LLM-based goal decomposition. This is migrated to `TaskPlanner` in Noet:

**From Goalith (LLMDecomposer)**:
- Takes a goal description
- Uses LLM structured output to produce sub-goals
- Returns ordered list of sub-goals with dependencies

**To Noet (TaskPlanner)** (defined in `noe-agent-impl.md` §5.2):
- Takes a goal string + context
- Uses LLM to produce a `TaskPlan` with ordered `TaskStep` items
- Supports plan revision based on reflection feedback

The key difference: TaskPlanner produces a flat plan with steps, not a recursive DAG. This is simpler and matches real agent workflows where depth-first decomposition is impractical.

### 2.2 GoalDecomposer ABC → Not Needed

The abstract `GoalDecomposer` hierarchy (`SimpleListDecomposer`, `CallableDecomposer`, `LLMDecomposer`) is over-engineered for the actual use case. A single `TaskPlanner` class with LLM-based planning and a fallback is sufficient.

---

## 3. Deprecation Plan

### Phase 1: Mark Deprecated (Immediate)

1. Add deprecation notice to `noesium/core/goalith/__init__.py`:

```python
"""
.. deprecated::
    The goalith module is deprecated and will be removed in a future release.
    Use TaskPlanner from noesium.agents.noe.planner for goal decomposition.
    Use LangGraph StateGraph for workflow DAGs.
    Use ExecutionProjection for task state tracking.
"""
import warnings
warnings.warn(
    "noesium.core.goalith is deprecated. "
    "Use Noet's TaskPlanner for goal decomposition.",
    DeprecationWarning,
    stacklevel=2,
)
```

2. Update `AGENTS.md` to remove Goalith references or mark as deprecated.
3. Remove or mark broken example `examples/goals/goalith_decomposer.py` as deprecated.

### Phase 2: Remove (Next Release)

1. Delete `noesium/core/goalith/` directory.
2. Delete `tests/goalith/` directory.
3. Remove any references from `AGENTS.md`, `docs/`, `specs/`.
4. Remove `networkx` dependency if no longer needed elsewhere.

---

## 4. Files Affected

### 4.1 Files to Deprecate/Remove

| Path | Action |
|------|--------|
| `noesium/core/goalith/__init__.py` | Add deprecation warning (Phase 1), delete (Phase 2) |
| `noesium/core/goalith/errors.py` | Delete (Phase 2) |
| `noesium/core/goalith/service.py` | Delete (Phase 2) |
| `noesium/core/goalith/goalgraph/node.py` | Delete (Phase 2) |
| `noesium/core/goalith/goalgraph/graph.py` | Delete (Phase 2) |
| `noesium/core/goalith/decomposer/base.py` | Delete (Phase 2) |
| `noesium/core/goalith/decomposer/simple_decomposer.py` | Delete (Phase 2) |
| `noesium/core/goalith/decomposer/callable_decomposer.py` | Delete (Phase 2) |
| `noesium/core/goalith/decomposer/llm_decomposer.py` | Delete (Phase 2) |
| `noesium/core/goalith/decomposer/prompts.py` | Delete (Phase 2) |
| `noesium/core/goalith/conflict/` | Delete (Phase 2) |
| `noesium/core/goalith/replanner/` | Delete (Phase 2) |
| `tests/goalith/` | Delete (Phase 2) |
| `examples/goals/goalith_decomposer.py` | Mark deprecated or delete |

### 4.2 Files to Update

| Path | Change |
|------|--------|
| `AGENTS.md` | Remove/deprecate Goalith section |
| `docs/impl/gap-analysis.md` | Note Goalith deprecation decision |
| `specs/rfc-index.md` | No change (Goalith was never an RFC) |

### 4.3 Knowledge Extracted To

| Concept | Destination |
|---------|-------------|
| LLM goal decomposition | `noesium/agents/noe/planner.py` (TaskPlanner) |
| Goal node lifecycle | `noesium/core/projection/execution.py` (ExecutionProjection) |
| DAG-based workflows | LangGraph StateGraph (already exists) |
| Task replanning | Noet reflection + revise_plan nodes |

---

## 5. Testing Impact

### 5.1 Tests to Remove (Phase 2)

| Test File | Lines | Coverage |
|-----------|-------|----------|
| `tests/goalith/test_base_decomposer.py` | ~60 | GoalDecomposer ABC |
| `tests/goalith/test_goal_graph_node.py` | ~120 | GoalNode lifecycle |
| `tests/goalith/test_goal_graph.py` | ~200 | GoalGraph operations |
| `tests/goalith/test_simple_decomposer.py` | ~40 | SimpleListDecomposer |
| `tests/goalith/test_callable_decomposer.py` | ~40 | CallableDecomposer |
| `tests/goalith/test_integration.py` | ~100 | Graph + decomposers |

### 5.2 Replacement Coverage

The extracted functionality (goal decomposition) will be tested in:
- `tests/agents/noe/test_planner.py` -- TaskPlanner unit tests
- `tests/agents/noe/test_agent.py` -- NoeANoetegration tests

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| External user depends on Goalith | **Low** (no evidence of external use, not documented as public API) | Low | Deprecation warning in Phase 1 |
| Loss of goal decomposition capability | **None** | N/A | Extracted to TaskPlanner |
| Breaking existing tests | **Low** (tests are self-contained) | Low | Delete tests with module |
| Loss of conflict detection | **None** | N/A | Never implemented (stub) |

---

## 7. Conclusion

The Goalith module represents an early design that has been superseded by the event-driven architecture (RFC-0001 through RFC-1002). Its core value -- LLM-based goal decomposition -- is extracted into `TaskPlanner`. All other features (DAG tracking, lifecycle, persistence, conflict detection, replanning) are either stub implementations or better served by LangGraph + EventStore + projections.

> **Goalith served its purpose as a design sketch. The event-driven architecture makes it redundant. Extract what's useful, deprecate the rest.**

---

## Appendix: Revision History

| Date | Changes |
|------|---------|
| 2026-03-01 | Initial assessment and deprecation plan |
