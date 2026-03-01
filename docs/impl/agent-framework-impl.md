# Agent Framework Implementation Architecture

> Implementation guide for LangGraph-based agents in Noesium.
>
> **Module**: `noesium/agents/`, `noesium/core/agent/`
> **Source**: Derived from [RFC-1002](../../specs/RFC-1002.md) (LangGraph-Based Agent Implementation Design)
> **Related RFCs**: [RFC-0003](../../specs/RFC-0003.md), [RFC-0005](../../specs/RFC-0005.md), [RFC-1001](../../specs/RFC-1001.md)

---

## 1. Overview

This guide describes how to implement and extend LangGraph-based agents in Noesium following the three archetypes defined in RFC-1002: Conversation, Research, and Task agents. It covers the practical steps for building agents, from state model design through graph construction to testing.

**Language**: Python 3.11+
**Key dependencies**: LangGraph, LangChain Core, Pydantic v2, instructor

---

## 2. Architectural Position

```
┌────────────────────────────────────────────────────────┐
│                   Concrete Agents                       │
│  AskuraAgent   SearchAgent   DeepResearchAgent   ...   │
└──────────┬─────────┬──────────────┬────────────────────┘
           │         │              │
    ┌──────▼───┐ ┌───▼─────┐ ┌─────▼──────┐
    │Conversa- │ │  Task   │ │  Research  │    Archetypes
    │tion Base │ │  Base   │ │  Base      │
    └──────┬───┘ └───┬─────┘ └─────┬──────┘
           │         │              │
    ┌──────▼─────────▼──────────────▼──────┐
    │       BaseGraphicAgent               │
    │  (StateGraph, KernelExecutor)        │
    └──────────────┬───────────────────────┘
                   │
    ┌──────────────▼───────────────────────┐
    │           BaseAgent                   │
    │  (LLM, logging, token tracking)      │
    └──────────────────────────────────────┘
```

---

## 3. Module Structure

### 3.1 Core Agent Base (`core/agent/`)

```
noesium/core/agent/
├── __init__.py          # Public exports
├── base.py              # BaseAgent, BaseGraphicAgent (existing, to be extended)
├── conversation.py      # BaseHitlAgent (extract from base.py)
└── researcher.py        # BaseResearcher, ResearchOutput (extract from base.py)
```

**Refactoring note**: Currently all base classes are in `base.py`. RFC-1002 recommends splitting into separate files for maintainability. This is a non-breaking refactor — update `__init__.py` to re-export from new locations.

### 3.2 Agent Implementations (`agents/`)

Each agent follows a consistent structure:

```
noesium/agents/<agent_name>/
├── __init__.py          # Public exports
├── agent.py             # Main agent class
├── state.py             # State TypedDict/BaseModel definitions
├── models.py            # Domain models (config, response, etc.)
├── prompts.py           # Prompt templates
├── schemas.py           # Structured LLM output models (instructor)
└── <components>.py      # Domain-specific modules
```

---

## 4. Core Types

### 4.1 State Models

**TypedDict pattern** (Research, Task agents):

```python
# agents/my_agent/state.py
import operator
from typing import Any, TypedDict
from typing_extensions import Annotated
from langgraph.graph import add_messages

class MyAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    results: Annotated[list, operator.add]
    loop_count: int
    max_loops: int
    context: dict[str, Any]
```

**Pydantic pattern** (Conversation agents):

```python
# agents/my_agent/models.py
from typing import Any, Sequence
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage

class MyConversationState(BaseModel):
    user_id: str = ""
    session_id: str = ""
    turns: int = 0
    messages: Sequence[BaseMessage] = Field(default_factory=list)
    extracted_info: dict[str, Any] = Field(default_factory=dict)
    is_complete: bool = False
    requires_user_input: bool = True
```

**Phase-specific state** (for Send fan-out):

```python
# agents/my_agent/state.py
class WorkerInput(TypedDict):
    task_id: str
    query: str

class WorkerOutput(TypedDict):
    task_id: str
    result: str
```

### 4.2 Configuration Models

```python
# agents/my_agent/models.py
class MyAgentConfig(BaseModel):
    llm_provider: str = "openai"
    model_name: str | None = None
    temperature: float = 0.7
    max_tokens: int = 1000
    # Domain-specific
    max_iterations: int = 3
    feature_flag: bool = False
```

### 4.3 Response Models

```python
# agents/my_agent/models.py
class MyAgentResponse(BaseModel):
    message: str
    session_id: str = ""
    is_complete: bool = False
    confidence: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### 4.4 Structured LLM Output Models

```python
# agents/my_agent/schemas.py
from pydantic import BaseModel, Field

class QueryPlan(BaseModel):
    queries: list[str] = Field(description="Search queries to execute")
    rationale: str = Field(description="Reasoning for chosen queries")

class EvaluationResult(BaseModel):
    is_sufficient: bool = Field(description="Whether gathered info is sufficient")
    knowledge_gap: str = Field(description="Summary of missing information")
    follow_up: list[str] = Field(description="Follow-up queries if needed")
```

---

## 5. Key Interfaces

### 5.1 BaseGraphicAgent Contract

All LangGraph agents MUST implement:

```python
class MyAgent(BaseGraphicAgent):
    def get_state_class(self) -> Type:
        """Return the state class for the graph."""
        return MyState

    def _build_graph(self) -> StateGraph:
        """Build and compile the agent's graph."""
        workflow = StateGraph(self.get_state_class())
        # ... add nodes, edges
        return workflow.compile()

    async def run(self, user_message: str, context=None, config=None) -> str:
        """Execute the agent."""
        ...
```

### 5.2 BaseHitlAgent Contract

Conversation agents MUST additionally implement:

```python
class MyConversationAgent(BaseHitlAgent):
    def start_conversation(self, user_id: str, initial_message: str = None) -> Response:
        """Start a new conversation session."""
        ...

    def process_user_message(self, user_id: str, session_id: str, message: str) -> Response:
        """Process a message within an existing session."""
        ...
```

### 5.3 BaseResearcher Contract

Research agents MUST additionally implement:

```python
class MyResearchAgent(BaseResearcher):
    async def research(self, user_message: str, context=None, config=None) -> ResearchOutput:
        """Execute research workflow."""
        ...
```

---

## 6. Implementation Details

### 6.1 Graph Construction Pattern

Follow this canonical order in `_build_graph()`:

```python
def _build_graph(self) -> StateGraph:
    state_class = self.get_state_class()
    workflow = StateGraph(state_class)

    # Step 1: Add all nodes
    workflow.add_node("node_a", self._node_a_node)
    workflow.add_node("node_b", self._node_b_node)

    # Step 2: Set entry edge
    workflow.add_edge(START, "node_a")

    # Step 3: Add sequential edges
    workflow.add_edge("node_a", "node_b")

    # Step 4: Add conditional edges
    workflow.add_conditional_edges("node_b", self._router, {"next": "node_c", "end": END})

    # Step 5: Add terminal edges
    workflow.add_edge("node_c", END)

    # Step 6: Compile with options
    return workflow.compile(
        checkpointer=self.checkpointer,        # If HITL needed
        interrupt_before=["human_review"],      # If HITL needed
    )
```

### 6.2 Node Implementation Pattern

```python
async def _process_node(self, state: MyState, config: RunnableConfig) -> dict:
    """
    Pattern:
    1. Log entry
    2. Extract needed state
    3. Perform computation
    4. Return state delta
    """
    logger.info("Process: Starting")

    query = state["query"]

    try:
        result = await self._perform_processing(query)
        logger.info(f"Process: Completed with {len(result)} items")
        return {"results": result, "status": "completed"}
    except Exception as e:
        logger.error(f"Process: Failed - {e}")
        raise RuntimeError(f"Processing failed: {e}")
```

### 6.3 Conditional Routing Pattern

```python
def _my_router(self, state: MyState) -> str:
    """Route based on state evaluation."""
    if state["is_complete"]:
        return "finalize"
    if state["loop_count"] >= state["max_loops"]:
        return "finalize"
    return "continue"
```

### 6.4 Fan-Out with Send Pattern

```python
def _dispatch_workers(self, state: QueryState) -> list[Send]:
    """Dispatch parallel workers via Send."""
    return [
        Send("worker", WorkerInput(task_id=str(i), query=q))
        for i, q in enumerate(state["queries"])
    ]
```

### 6.5 HITL Pattern

```python
# In _build_graph():
builder.compile(
    checkpointer=InMemorySaver(),
    interrupt_before=["human_review"],
)

# In execution:
def _run_graph(self, state: MyState) -> tuple[Response, MyState]:
    config = RunnableConfig(
        configurable={"thread_id": state.session_id},
        recursion_limit=self.config.max_turns,
        callbacks=[NodeLoggingCallback(), TokenUsageCallback(model_name=self.config.model_name)],
    )
    result = self.graph.invoke(state, config)
    return self._create_response(result), result
```

### 6.6 Structured LLM Completion Pattern

```python
async def _generate_plan_node(self, state: MyState, config: RunnableConfig) -> dict:
    prompt = self._format_prompt(state)

    try:
        result: QueryPlan = self.llm_client.structured_completion(
            messages=[{"role": "user", "content": prompt}],
            response_model=QueryPlan,
            temperature=0.7,
            max_tokens=1000,
        )
        return {"queries": result.queries, "rationale": result.rationale}
    except Exception as e:
        logger.error(f"Structured completion failed: {e}")
        return {"queries": [state["original_query"]], "rationale": "Fallback to original"}
```

---

## 7. Error Handling

### 7.1 Node-Level Errors

Nodes SHOULD catch domain-specific exceptions and re-raise as `RuntimeError`:

```python
async def _search_node(self, state, config):
    try:
        return await self._perform_search(state)
    except SearchAPIError as e:
        logger.error(f"Search API error: {e}")
        raise RuntimeError(f"Search failed: {e}")
```

### 7.2 Graph-Level Errors

Agent `run()` MUST catch all graph execution errors:

```python
async def run(self, user_message, **kwargs):
    try:
        result = await self.graph.ainvoke(initial_state, config=config)
        return self._format_result(result)
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        return f"Error: {e}"
```

### 7.3 Conversation Error Responses

Conversation agents return structured error responses:

```python
def _create_error_response(self, state, error_msg):
    return MyResponse(
        message=f"An error occurred: {error_msg}",
        session_id=state.session_id,
        is_complete=False,
        requires_user_input=True,
        metadata={"error": error_msg},
    )
```

---

## 8. Configuration

### 8.1 Agent Initialization Pattern

```python
class MyAgent(BaseGraphicAgent):
    def __init__(self, config: MyAgentConfig):
        super().__init__(
            llm_provider=config.llm_provider,
            model_name=config.model_name,
        )
        self.config = config

        # Initialize domain components
        self.processor = MyProcessor(config)

        # Build graph
        self.graph = self._build_graph()
```

### 8.2 Multi-LLM Configuration

Agents MAY use different LLM clients for different roles:

```python
def __init__(self, config):
    super().__init__(llm_provider=config.llm_provider)
    self.planning_llm = config.planning_llm or self.llm
    self.execution_llm = config.execution_llm or self.llm
    self.reflection_llm = config.reflection_llm or self.llm
```

---

## 9. Testing Strategy

### 9.1 Unit Tests

| Component | Test Focus |
|-----------|------------|
| State models | Serialization, defaults, reducer behavior |
| Individual nodes | Input/output contract, error handling |
| Routers | Routing decisions for all branches |
| Config models | Validation, defaults |

### 9.2 Graph Integration Tests

```python
async def test_search_agent_full_flow():
    agent = SearchAgent(llm_provider="openai", search_engines=["tavily"])
    result = await agent.run("Python web frameworks 2025")
    assert "results" in result.lower() or len(result) > 0

async def test_conversation_agent_multi_turn():
    agent = MyConversationAgent(config=MyConfig())
    r1 = agent.start_conversation("user1", "Hello")
    assert r1.requires_user_input
    r2 = agent.process_user_message("user1", r1.session_id, "Tell me more")
    assert r2.session_id == r1.session_id
```

### 9.3 Node-Level Tests

```python
async def test_reflection_node():
    agent = DeepResearchAgent()
    state = ResearchState(
        messages=[HumanMessage(content="test")],
        search_summaries=["summary 1", "summary 2"],
        research_loop_count=1,
        max_research_loops=3,
    )
    result = agent._reflection_node(state, config=RunnableConfig())
    assert "is_sufficient" in result
    assert "follow_up_queries" in result
```

### 9.4 Mock Patterns

For testing nodes that call LLMs:

```python
from unittest.mock import MagicMock, AsyncMock

def test_with_mock_llm():
    agent = MyAgent(config=MyConfig())
    agent.llm = MagicMock()
    agent.llm.structured_completion.return_value = QueryPlan(
        queries=["test query"], rationale="test"
    )
    result = agent._generate_plan_node(state, config)
    assert result["queries"] == ["test query"]
```

---

## 10. Creating a New Agent: Step-by-Step

### Step 1: Define State Model

Choose TypedDict (Task/Research) or Pydantic BaseModel (Conversation).

### Step 2: Define Config and Response Models

Create `models.py` with `MyAgentConfig` and `MyAgentResponse`.

### Step 3: Define Structured Output Schemas

If using `structured_completion()`, create `schemas.py` with Pydantic models.

### Step 4: Write Prompt Templates

Create `prompts.py` with prompt strings or template functions.

### Step 5: Choose Base Class

| Agent Type | Base Class | Required Methods |
|------------|-----------|------------------|
| Task | `BaseGraphicAgent` | `get_state_class()`, `_build_graph()`, `run()` |
| Conversation | `BaseHitlAgent` | Above + `start_conversation()`, `process_user_message()` |
| Research | `BaseResearcher` | `get_state_class()`, `_build_graph()`, `research()` |

### Step 6: Implement Nodes

Write `_<name>_node()` methods following the node contract.

### Step 7: Build Graph

Implement `_build_graph()` wiring nodes and edges.

### Step 8: Test

Write unit tests for nodes, integration tests for full graph execution.

### Step 9: Create Demo

Add `examples/agents/<agent_name>_demo.py` showing basic usage.
