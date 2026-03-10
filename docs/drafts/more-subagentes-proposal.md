# Core Subagents Design Proposal

**Status**: Implemented
**Author**: Noesium Team
**Created**: 2026-03-10
**Implemented**: 2026-03-10
**Related**: RFC-1001, RFC-1002, RFC-1006, RFC-1007

---

## 1. Overview

This proposal defines three core subagents for the Noesium framework. These subagents are designed to be **independent of the NoeAgent project** and reside in the `noesium.subagents` layer, following the dependency direction defined in RFC-1007:

```
core ← toolkits ← subagents ← noeagent
```

**Key Principle**: Subagents in `noesium.subagents` must only depend on `noesium.core` and `noesium.toolkits`, never on `noeagent`. This ensures reusability across different agent applications.

---

## 2. Design Principles

### 2.1 Independence

- Core subagents MUST NOT import from `noeagent` package
- Subagents MUST use only `noesium.core` primitives (BaseGraphicAgent, BaseLLMClient, etc.)
- Subagents MAY use tools from `noesium.toolkits` via dependency injection

### 2.2 Composability

- Subagents MAY call other subagents via `SubagentManager` interface (RFC-1006)
- Subagents MAY use tools injected at runtime
- Subagents MUST expose progress events via `astream_progress()` pattern

### 2.3 Capability-Based Tool Access

- Each subagent declares its required capabilities
- Tools are injected via configuration, not hardcoded imports
- Side-effect classification determines tool permissions (RFC-1003)

---

## 3. Agent Specifications

### 3.1 PlanAgent

**Purpose**: A general-purpose planning agent that generates detailed, actionable plans with structured steps, resource requirements, dependencies, and verification criteria. Applicable to diverse domains including software implementation, research projects, business workflows, content creation, and complex multi-step objectives.

**Location**: `noesium/subagents/plan/`

**Context Handling** (Unified):
PlanAgent uses smart context detection - it automatically determines whether to explore resources or use provided context:
- If `context` contains sufficient information, proceeds directly to planning
- If `context` is empty or insufficient, automatically triggers resource exploration
- Supports hybrid scenarios where partial context is enriched via exploration

**Capabilities**:
- Read-only resource access for context exploration
- User interaction for requirement clarification
- Subagent delegation (can call ExploreAgent for deeper analysis)
- Structured output with actionable steps and verification criteria
- Domain-agnostic planning (works for code, research, workflows, projects)

**Allowed Tools** (read-only):
| Toolkit | Allowed Functions |
|---------|-------------------|
| `file_edit` | `read_file`, `list_files`, `search_in_files`, `get_file_info` |
| `user_interaction` | All functions |
| `bash` | Read-only commands (ls, cat, find, grep) |
| `document` | Read-only document parsing |

**Graph Workflow**:
```
START → evaluate_context → [conditional: explore_resources if needed] → analyze_requirements → generate_detailed_plan → identify_dependencies → define_verification_steps → END
```

**State Model**:
```python
class PlanState(TypedDict):
    messages: List[AnyMessage]
    # Context (unified handling)
    context: Dict[str, Any]              # Provided or gathered context
    context_sufficient: bool             # Whether context is sufficient for planning
    explored_resources: List[str]        # Resources explored during context gathering
    # Planning
    requirements: List[Requirement]
    constraints: List[Constraint]
    plan_type: Literal["implementation", "research", "workflow", "project", "general"]
    plan: Optional[DetailedPlan]
    # Output
    plan_steps: List[PlanStep]
    dependencies: List[Dependency]
    verification_steps: List[VerificationStep]
```

**Output Models**:
```python
class PlanStep(TypedDict):
    step_id: str
    description: str
    action_type: Literal["create", "modify", "analyze", "execute", "research", "review", "deploy"]
    target: Optional[str]              # File, resource, or entity to act upon
    details: Optional[List[ActionDetail]]
    dependencies: List[str]            # Other step_ids this depends on
    verification: VerificationStep
    estimated_effort: Literal["low", "medium", "high"]
    resources_required: List[str]

class ActionDetail(TypedDict):
    aspect: str                        # What aspect is being addressed
    action: str                        # Specific action to take
    content: Optional[str]             # Suggested content, code, or approach
    rationale: str                     # Why this action is needed

class VerificationStep(TypedDict):
    type: Literal["test", "review", "validation", "manual", "automated", "milestone"]
    criteria: List[str]                # Success criteria
    method: Optional[str]              # How to verify
    expected_outcome: str              # What success looks like
```

**Planning Process**:

1. **Context Evaluation**
   - Assess provided context for completeness
   - Identify information gaps that require exploration
   - Determine plan type based on objective (implementation, research, workflow, project)

2. **Context Enrichment** (if needed)
   - Explore available resources to fill information gaps
   - Gather relevant materials, documentation, or data
   - Delegate to ExploreAgent for complex exploration tasks

3. **Requirement Analysis**
   - Parse objective into structured requirements
   - Identify constraints (time, resources, dependencies, compatibility)
   - Clarify ambiguities via user interaction if needed

4. **Plan Generation**
   - Decompose objective into ordered steps
   - Identify targets (files, resources, entities) for each step
   - Provide specific details and approaches for key actions
   - Map dependencies between steps

5. **Verification Definition**
   - Define success criteria for each step
   - Specify validation methods
   - Identify milestone checkpoints
   - List manual review requirements

**Plan Types Supported**:

| Plan Type | Description | Example Use Cases |
|-----------|-------------|-------------------|
| **Implementation** | Code or system changes | Add feature, refactor module, fix bug |
| **Research** | Investigation and analysis | Literature review, data analysis, feasibility study |
| **Workflow** | Process execution | Deployment pipeline, data processing, migration |
| **Project** | Multi-phase objectives | Product launch, system upgrade, team onboarding |

**Example Output (Implementation Plan)**:
```python
{
    "plan_type": "implementation",
    "plan_steps": [
        {
            "step_id": "step-001",
            "description": "Add authentication middleware",
            "action_type": "create",
            "target": "src/middleware/auth.py",
            "details": [
                {
                    "aspect": "core logic",
                    "action": "Implement JWT validation",
                    "content": "class AuthMiddleware: ...",
                    "rationale": "Enable token-based authentication"
                }
            ],
            "dependencies": [],
            "verification": {
                "type": "test",
                "criteria": ["JWT tokens validated correctly", "Invalid tokens rejected"],
                "method": "pytest tests/test_auth.py",
                "expected_outcome": "All auth tests pass"
            }
        }
    ]
}
```

**Example Output (Research Plan)**:
```python
{
    "plan_type": "research",
    "plan_steps": [
        {
            "step_id": "step-001",
            "description": "Literature review on transformer architectures",
            "action_type": "research",
            "target": "academic databases",
            "details": [
                {
                    "aspect": "primary sources",
                    "action": "Search ArXiv for attention mechanisms",
                    "content": "query: 'attention mechanism' AND 'transformer'",
                    "rationale": "Establish theoretical foundation"
                }
            ],
            "dependencies": [],
            "verification": {
                "type": "milestone",
                "criteria": ["10+ relevant papers identified", "Key concepts documented"],
                "method": "Review findings summary",
                "expected_outcome": "Comprehensive literature summary"
            }
        }
    ]
}
```

---

### 3.2 ExploreAgent

**Purpose**: A general-purpose exploration agent that discovers and synthesizes essential information from diverse sources - files, documents, media, data, and structured content. Designed for information gathering across any domain including code analysis, document research, data exploration, and multi-modal content analysis.

**Location**: `noesium/subagents/explore/`

**Capabilities**:
- Multi-modal resource exploration (code, documents, images, audio, video, data)
- Iterative discovery with reflection-based quality control
- Progress streaming for long-running explorations
- Structured findings with source citations and confidence scores
- Domain-agnostic (works for code, research, data, content)

**Allowed Tools** (read-only):
| Toolkit | Allowed Functions |
|---------|-------------------|
| `file_edit` | `read_file`, `list_files`, `search_in_files`, `get_file_info` |
| `bash` | Read-only commands (ls, cat, head, tail, grep, find) |
| `python_executor` | Read-only execution (no file writes) |
| `document` | Read-only document parsing (PDF, Word, etc.) |
| `audio` | `transcribe_audio`, `get_audio_info` |
| `image` | Read-only image analysis |
| `video` | Read-only video analysis |
| `tabular_data` | Read-only data analysis (CSV, Excel) |

**Graph Workflow**:
```
START → parse_target → generate_search_strategy → [parallel: explore_sources] → reflect → [loop if insufficient] → synthesize_findings → END
```

**State Model**:
```python
class ExploreState(TypedDict):
    messages: List[AnyMessage]
    target: str                          # What to explore
    target_type: Literal["code", "document", "data", "media", "general"]
    # Exploration
    search_strategy: List[SearchQuery]
    findings: List[Finding]
    sources: List[Source]
    tool_results: List[Dict[str, Any]]
    # Reflection loop
    reflection: Optional[ReflectionResult]
    exploration_loops: int
    max_loops: int
    is_sufficient: bool
    # Output
    summary: Optional[str]
    confidence_score: float
```

**Output Models**:
```python
class Finding(TypedDict):
    finding_id: str
    title: str
    description: str
    source: str                          # Where this finding came from
    relevance: Literal["high", "medium", "low"]
    finding_type: Literal["fact", "pattern", "insight", "reference"]
    details: Dict[str, Any]              # Additional structured data

class Source(TypedDict):
    source_id: str
    type: Literal["file", "document", "data", "media", "url"]
    name: str
    location: str
    summary: str
    accessed_at: str

class ReflectionResult(TypedDict):
    is_sufficient: bool
    knowledge_gaps: List[str]
    follow_up_queries: List[str]
    confidence: float
    reasoning: str

class ExploreResult(TypedDict):
    target: str
    summary: str
    findings: List[Finding]
    sources: List[Source]
    confidence_score: float
    exploration_depth: int
    metadata: Dict[str, Any]
```

**Exploration Process**:

1. **Target Analysis**
   - Parse exploration target into structured query
   - Determine target type (code, document, data, media)
   - Identify appropriate tools and search strategies

2. **Strategy Generation**
   - Create multi-pronged search strategy
   - Prioritize high-relevance sources
   - Plan parallel exploration paths

3. **Source Exploration**
   - Execute search strategies in parallel where possible
   - Gather findings from each source
   - Track source citations and access metadata

4. **Reflection Loop**
   - Evaluate completeness of gathered information
   - Identify knowledge gaps
   - Generate follow-up queries if needed
   - Loop until sufficient or max depth reached

5. **Synthesis**
   - Aggregate findings across all sources
   - Generate coherent summary
   - Calculate confidence score
   - Produce structured ExploreResult

---

### 3.3 DavinciAgent

**Purpose**: A scientific research agent for academic and research workflows.

**Location**: `noesium/subagents/davinci/`

**Status**: Placeholder for future implementation

**Planned Capabilities**:
- ArXiv paper search and analysis
- Literature review synthesis
- Research hypothesis generation
- Citation management

**Planned Tools**:
| Toolkit | Functions |
|---------|-----------|
| `arxiv` | Paper search, metadata retrieval |
| `web_search` | Academic search engines |
| `document` | PDF parsing, citation extraction |
| `jina_research` | Web content extraction |

---

## 4. Implementation Guide

### 4.1 Directory Structure

```
noesium/src/noesium/subagents/
├── __init__.py
├── askura/           # Existing: conversation agent
├── tacitus/          # Existing: research agent
├── plan/             # NEW: PlanAgent
│   ├── __init__.py
│   ├── agent.py
│   ├── state.py
│   ├── prompts.py
│   └── schemas.py
├── explore/          # NEW: ExploreAgent
│   ├── __init__.py
│   ├── agent.py
│   ├── state.py
│   ├── prompts.py
│   └── schemas.py
└── davinci/          # FUTURE: DavinciAgent
    └── __init__.py   # Placeholder
```

### 4.2 Base Class Pattern

All subagents extend `BaseGraphicAgent` from `noesium.core.agent`:

```python
from noesium.core.agent import BaseGraphicAgent
from noesium.core.utils.typing import override

class PlanAgent(BaseGraphicAgent):
    def __init__(self, config: PlanConfig, tools: Optional[Dict[str, Any]] = None):
        super().__init__(llm_provider=config.llm_provider)
        self.config = config
        self.tools = tools or {}
        self.graph = self._build_graph()

    @override
    def get_state_class(self) -> Type:
        return PlanState

    @override
    def _build_graph(self) -> StateGraph:
        # Build LangGraph workflow
        ...

    async def astream_progress(self, target: str, context: Dict[str, Any] = None) -> AsyncGenerator[ProgressEvent, None]:
        # Stream progress events (follow TacitusAgent pattern)
        ...
```

### 4.3 Tool Injection Pattern

Tools are injected via configuration, not hardcoded:

```python
# Good: Tool injection via config
config = PlanConfig(
    llm_provider="openai",
    allowed_tools=["read_file", "list_files", "search_in_files"]
)
agent = PlanAgent(config, tools=tool_registry.get_tools(config.allowed_tools))

# Bad: Hardcoded tool imports inside agent
from noesium.toolkits.file_edit import read_file  # DON'T DO THIS
```

### 4.4 Progress Event Pattern

Follow TacitusAgent's `astream_progress()` pattern for real-time feedback:

```python
async def astream_progress(self, target: str, context: Dict = None) -> AsyncGenerator[ProgressEvent, None]:
    from noesium.core.event import ProgressEvent, ProgressEventType

    session_id = uuid7str()

    yield ProgressEvent(
        type=ProgressEventType.SESSION_START,
        session_id=session_id,
        summary=f"Planning: {target[:60]}"
    )

    # ... workflow execution with progress events ...

    yield ProgressEvent(
        type=ProgressEventType.SESSION_END,
        session_id=session_id
    )
```

### 4.5 Output Schema Definitions

Full Pydantic model definitions for structured outputs:

**schemas.py for PlanAgent**:
```python
"""Structured output schemas for PlanAgent."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ActionDetail(BaseModel):
    """Details about a specific action within a plan step."""
    aspect: str = Field(..., description="What aspect is being addressed")
    action: str = Field(..., description="Specific action to take")
    content: Optional[str] = Field(None, description="Suggested content or approach")
    rationale: str = Field(..., description="Why this action is needed")


class VerificationStep(BaseModel):
    """Verification criteria for a plan step."""
    type: Literal["test", "review", "validation", "manual", "automated", "milestone"]
    criteria: List[str] = Field(default_factory=list, description="Success criteria")
    method: Optional[str] = Field(None, description="How to verify")
    expected_outcome: str = Field(..., description="What success looks like")


class PlanStep(BaseModel):
    """A single step in a plan."""
    step_id: str = Field(..., description="Unique step identifier")
    description: str = Field(..., description="What this step accomplishes")
    action_type: Literal["create", "modify", "analyze", "execute", "research", "review", "deploy"]
    target: Optional[str] = Field(None, description="File, resource, or entity to act upon")
    details: Optional[List[ActionDetail]] = Field(None, description="Detailed actions")
    dependencies: List[str] = Field(default_factory=list, description="Step IDs this depends on")
    verification: VerificationStep
    estimated_effort: Literal["low", "medium", "high"] = "medium"
    resources_required: List[str] = Field(default_factory=list)


class Dependency(BaseModel):
    """Dependency relationship between steps."""
    from_step: str = Field(..., description="Dependent step ID")
    to_step: str = Field(..., description="Required step ID")
    reason: str = Field(..., description="Why this dependency exists")


class DetailedPlan(BaseModel):
    """Complete structured plan output."""
    plan_type: Literal["implementation", "research", "workflow", "project", "general"]
    title: str
    summary: str
    plan_steps: List[PlanStep]
    dependencies: List[Dependency] = Field(default_factory=list)
    estimated_total_effort: Literal["low", "medium", "high"] = "medium"
    prerequisites: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

**schemas.py for ExploreAgent**:
```python
"""Structured output schemas for ExploreAgent."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class Finding(BaseModel):
    """A single finding from exploration."""
    finding_id: str = Field(..., description="Unique finding identifier")
    title: str = Field(..., description="Brief title of the finding")
    description: str = Field(..., description="Detailed description")
    source: str = Field(..., description="Where this finding came from")
    relevance: Literal["high", "medium", "low"] = "medium"
    finding_type: Literal["fact", "pattern", "insight", "reference"] = "fact"
    details: Dict[str, Any] = Field(default_factory=dict)


class Source(BaseModel):
    """A source accessed during exploration."""
    source_id: str = Field(..., description="Unique source identifier")
    type: Literal["file", "document", "data", "media", "url"]
    name: str = Field(..., description="Source name or title")
    location: str = Field(..., description="Path or URL")
    summary: str = Field(..., description="Brief summary of content")
    accessed_at: str = Field(..., description="ISO timestamp")


class ReflectionResult(BaseModel):
    """Result of reflection on exploration progress."""
    is_sufficient: bool = Field(..., description="Whether gathered info is sufficient")
    knowledge_gaps: List[str] = Field(default_factory=list)
    follow_up_queries: List[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    reasoning: str = Field(..., description="Explanation of assessment")


class ExploreResult(BaseModel):
    """Complete exploration result."""
    target: str = Field(..., description="Original exploration target")
    summary: str = Field(..., description="Synthesized summary of findings")
    findings: List[Finding] = Field(default_factory=list)
    sources: List[Source] = Field(default_factory=list)
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    exploration_depth: int = Field(0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### 4.6 Generalized Prompt Templates

Domain-agnostic prompts for general-purpose operation:

**prompts.py for PlanAgent**:
```python
"""General-purpose prompts for PlanAgent."""

PLAN_SYSTEM_PROMPT = """You are an expert planning agent capable of creating detailed, actionable plans for any domain.

Your responsibilities:
1. Analyze objectives and requirements
2. Break down complex tasks into clear, ordered steps
3. Identify dependencies between steps
4. Define verification criteria for each step
5. Provide specific, actionable guidance

You work across domains including:
- Software implementation (code, systems, infrastructure)
- Research and analysis (literature review, data analysis, feasibility)
- Business workflows (processes, pipelines, operations)
- Projects (multi-phase initiatives, launches, migrations)
- General tasks (content creation, documentation, organization)

Guidelines:
- Assess provided context before planning
- Request clarification if requirements are ambiguous
- Break tasks into specific, verifiable steps
- Include rationale for each step
- Identify dependencies and prerequisites
- Estimate effort for each step
- Define clear success criteria

You have access to:
- File and document reading tools (read_file, list_files, search_in_files)
- User interaction tools (ask_question)

You do NOT have write access - you only create plans, not implementations.
"""

CONTEXT_EVALUATION_PROMPT = """Evaluate the provided context for the following objective.

Objective: {objective}

Provided Context:
{context}

Determine:
1. Is the context sufficient to create a detailed plan?
2. What information gaps exist?
3. What resources should be explored to fill gaps?
4. What is the likely plan type (implementation, research, workflow, project)?

Respond with a structured assessment.
"""

PLAN_GENERATION_PROMPT = """Create a detailed, actionable plan for the following objective.

Objective: {objective}

Context: {context}

Plan Type: {plan_type}

Requirements:
1. Break down into clear, numbered steps
2. For each step provide:
   - Description of what to accomplish
   - Action type (create, modify, analyze, execute, research, review, deploy)
   - Target resource or entity (if applicable)
   - Detailed actions with rationale
   - Dependencies on other steps
   - Verification criteria
   - Effort estimate (low/medium/high)
3. Identify overall dependencies and prerequisites
4. Note potential risks or blockers

Format as a structured plan with clear, actionable steps.
"""
```

**prompts.py for ExploreAgent**:
```python
"""General-purpose prompts for ExploreAgent."""

EXPLORE_SYSTEM_PROMPT = """You are an expert exploration agent capable of gathering and synthesizing information from diverse sources.

Your responsibilities:
1. Analyze exploration targets
2. Develop effective search strategies
3. Gather information from multiple source types
4. Evaluate completeness of findings
5. Synthesize clear, actionable summaries

You work across source types including:
- Files and code (source code, configuration, scripts)
- Documents (PDFs, Word docs, text files, markdown)
- Data (CSV, Excel, databases, JSON)
- Media (images, audio, video)
- Structured content (APIs, logs, outputs)

Guidelines:
- Identify the target type before exploring
- Use appropriate tools for each source type
- Track all sources and citations
- Evaluate relevance of each finding
- Reflect on completeness before synthesizing
- Provide confidence scores for findings

You have access to:
- File operations (read_file, list_files, search_in_files, get_file_info)
- Shell commands (read-only: ls, cat, head, tail, grep, find)
- Python execution (read-only analysis)
- Document parsing (PDF, Word)
- Media analysis (audio transcription, image analysis, video analysis)
- Data analysis (CSV, Excel, tabular data)

You do NOT have write access - you only gather information.
"""

TARGET_ANALYSIS_PROMPT = """Analyze the following exploration target.

Target: {target}

Context: {context}

Determine:
1. Target type (code, document, data, media, general)
2. What information is being sought
3. Which tools would be most effective
4. What sources should be prioritized
5. Appropriate exploration depth
"""

REFLECTION_PROMPT = """Reflect on the exploration progress.

Target: {target}

Findings so far:
{findings}

Sources accessed:
{sources}

Evaluate:
1. Is the gathered information sufficient?
2. What knowledge gaps remain?
3. What follow-up queries would fill gaps?
4. Confidence level (0.0 to 1.0)

Provide reasoning for your assessment.
"""

SYNTHESIS_PROMPT = """Synthesize all findings into a comprehensive summary.

Target: {target}

Findings:
{findings}

Sources:
{sources}

Create a clear, organized summary that:
1. Directly addresses the exploration target
2. Highlights key findings with relevance
3. Provides actionable insights
4. References specific sources
5. Notes any gaps or limitations
6. Includes a confidence score
"""
```

---

## 5. Testing Requirements

### 5.1 Unit Tests

Each agent requires unit tests covering:
- Graph node functions in isolation
- State transitions
- Tool invocation with mocked dependencies
- Error handling and edge cases

**Location**: `noesium/tests/subagents/test_plan_agent.py`, `test_explore_agent.py`

### 5.2 Integration Tests

Integration tests covering:
- Full workflow execution with real LLM (or mock)
- Tool integration with actual toolkits
- Progress event streaming
- Subagent-to-subagent delegation

**Location**: `noesium/tests/integration/test_subagents.py`

---

## 6. Examples

Each agent should include a usage example:

- `examples/subagents/plan_demo.py` - PlanAgent demonstration
- `examples/subagents/explore_demo.py` - ExploreAgent demonstration

---

## 7. Tasks

- [x] Implement `PlanAgent` with graph workflow
- [x] Implement `ExploreAgent` with reflection loop
- [ ] Create unit tests for both agents
- [ ] Create integration tests
- [ ] Write usage examples
- [ ] Update documentation and RFC index
- [ ] (Future) Implement `DavinciAgent`

---

## 8. References

- [RFC-1001](../specs/RFC-1001.md) - Core Agent Architecture
- [RFC-1002](../specs/RFC-1002.md) - Projection and Memory Model
- [RFC-1006](../specs/RFC-1006.md) - Subagent Orchestration
- [RFC-1007](../specs/RFC-1007.md) - Layer Architecture
- [RFC-1010](../specs/RFC-1010.md) - CognitiveContext
- [TacitusAgent](../../noesium/src/noesium/subagents/tacitus/agent.py) - Reference implementation
- [AskuraAgent](../../noesium/src/noesium/subagents/askura/agent.py) - Reference implementation

---

## 9. Implementation Status and Gap Analysis

### 9.1 Current Implementation Status

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| PlanAgent | `noesium/src/noesium/subagents/plan/` | Complete | General-purpose planning with unified context handling |
| ExploreAgent | `noesium/src/noesium/subagents/explore/` | Complete | Reflection loop with iterative quality control |
| DavinciAgent | `noesium/src/noesium/subagents/davinci/` | Placeholder | Future implementation |
| Plan schemas | `plan/schemas.py` | Complete | Pydantic models for structured output |
| Explore schemas | `explore/schemas.py` | Complete | Pydantic models for structured output |

### 9.2 Gap Analysis

All gaps have been resolved (2026-03-10):

| Gap | Proposal | Implementation Status |
|-----|----------|----------------------|
| **General-purpose prompts** | Domain-agnostic prompts | ✅ Implemented in `prompts.py` |
| **Structured output schemas** | Pydantic models (PlanStep, Finding, etc.) | ✅ Implemented in `schemas.py` |
| **Reflection loop** | ExploreAgent has reflect node with loop | ✅ Conditional routing with `_should_continue_exploring` |
| **Plan type classification** | 4 plan types supported | ✅ Detected in `evaluate_context_node` |
| **Context sufficiency check** | Smart context evaluation | ✅ `ContextEvaluation` with structured output |
| **Confidence scoring** | ExploreResult.confidence_score | ✅ Calculated in reflection and synthesis |

### 9.3 Implementation Files Reference

**PlanAgent**:
- Agent: [`noesium/src/noesium/subagents/plan/agent.py`](../../noesium/src/noesium/subagents/plan/agent.py)
- State: [`noesium/src/noesium/subagents/plan/state.py`](../../noesium/src/noesium/subagents/plan/state.py)
- Prompts: [`noesium/src/noesium/subagents/plan/prompts.py`](../../noesium/src/noesium/subagents/plan/prompts.py)

**ExploreAgent**:
- Agent: [`noesium/src/noesium/subagents/explore/agent.py`](../../noesium/src/noesium/subagents/explore/agent.py)
- State: [`noesium/src/noesium/subagents/explore/state.py`](../../noesium/src/noesium/subagents/explore/state.py)
- Prompts: [`noesium/src/noesium/subagents/explore/prompts.py`](../../noesium/src/noesium/subagents/explore/prompts.py)

### 9.4 Migration Checklist

Implementation completed on 2026-03-10:

**PlanAgent**:
- [x] Add `schemas.py` with Pydantic models from Section 4.5
- [x] Update `state.py` with unified context handling fields
- [x] Replace `prompts.py` with general-purpose prompts from Section 4.6
- [x] Add `evaluate_context` node to workflow
- [x] Add plan type detection and handling
- [x] Update `_generate_plan_node` to use structured output

**ExploreAgent**:
- [x] Add `schemas.py` with Pydantic models from Section 4.5
- [x] Update `state.py` with target_type and reflection fields
- [x] Replace `prompts.py` with general-purpose prompts from Section 4.6
- [x] Add reflection node with conditional loop
- [x] Add confidence score calculation
- [x] Update `_synthesize_node` to produce ExploreResult