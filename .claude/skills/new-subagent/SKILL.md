---
name: new-subagent
description: Creates new subagents for the noesium framework following architectural patterns including BaseGraphicAgent inheritance, LangGraph workflows, progress event streaming, and SubagentProtocol implementation. Use when building new AI agents that need state management, tool access, and progress reporting.
metadata:
  author: noesium
  version: 1.0.0
---

# Create New Subagent

Comprehensive guide for creating new subagents in the noesium framework with progress events, state management, and tool integration.

## When to Use

- Creating a new AI agent with stateful execution
- Building agents that need progress reporting
- Implementing tools-aware agents
- Developing domain-specific AI workflows
- Adding new agent capabilities to noesium

## Architecture Overview

Noesium subagents follow a consistent architecture:

1. **Inherit from `BaseGraphicAgent`** - Provides LangGraph integration
2. **Define state class** - TypedDict for workflow state
3. **Build workflow graph** - StateGraph with nodes and edges
4. **Stream progress events** - Real-time execution feedback
5. **Register with manager** - Make discoverable and invokable

## Step-by-Step Process

### 1. Plan the Subagent

Before writing code, determine:

**Purpose and Scope:**
- What task does this agent perform?
- What inputs does it need?
- What outputs does it produce?
- Does it need tool access?
- What progress events are meaningful?

**Task Types:**
- Define keywords for agent selection
- Set cost/latency hints
- Determine concurrency needs

Example planning:
```python
# Task: Research agent with web search
# Inputs: Query string, optional context
# Outputs: Structured research report
# Tools: web_search, read_file
# Events: thinking, tool calls, progress updates
# Cost: HIGH (uses external APIs)
# Latency: BATCH (research takes time)
```

### 2. Create Directory Structure

Create a new directory under `noesium/src/noesium/subagents/`:

```
subagents/
└── my-agent/
    ├── __init__.py        # Exports
    ├── agent.py           # Main agent class
    ├── state.py           # State definitions
    ├── schemas.py         # Input/output schemas
    ├── prompts.py         # System prompts (optional)
    └── tools.py           # Custom tools (optional)
```

### 3. Define State Class

Create `state.py` with TypedDict:

```python
from typing import TypedDict, Annotated
from operator import add

class MyAgentState(TypedDict):
    """State for my agent workflow."""

    # Input
    user_message: str
    context: dict

    # Accumulated results
    findings: Annotated[list[str], add]  # Auto-appended

    # Current step tracking
    current_step: str

    # Final output
    final_result: str | None

    # Error handling
    errors: Annotated[list[str], add]
```

**State Design Tips:**
- Use `Annotated[list, add]` for accumulators
- Keep state minimal but complete
- Include error tracking
- Consider checkpointing needs

### 4. Create Input/Output Schemas

Define `schemas.py` with Pydantic models:

```python
from pydantic import BaseModel, Field
from typing import Optional

class MyAgentInput(BaseModel):
    """Input schema for my agent."""

    query: str = Field(..., description="Research query")
    max_depth: int = Field(default=3, description="Maximum search depth")
    context: Optional[dict] = Field(default=None, description="Optional context")

class MyAgentOutput(BaseModel):
    """Output schema for my agent."""

    result: str = Field(..., description="Final result")
    findings: list[str] = Field(default_factory=list, description="Key findings")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    sources_used: list[str] = Field(default_factory=list, description="Sources consulted")
```

### 5. Implement Main Agent Class

Create `agent.py` with full implementation:

```python
from noesium.core.agent.base import BaseGraphicAgent
from noesium.core.agent.subagent.events import SubagentProgressEvent
from noesium.core.agent.subagent.descriptor import SubagentDescriptor, CostHint, LatencyHint
from noesium.core.agent.subagent.context import SubagentContext
from noesium.core.event import ProgressEvent, ProgressEventType
from noesium.core.tool.helper import create_tool_helper, ToolHelper
from langgraph.graph import StateGraph, START, END
from typing import AsyncGenerator, Type
import uuid

from .state import MyAgentState
from .schemas import MyAgentInput, MyAgentOutput

class MyAgent(BaseGraphicAgent):
    """
    Agent for performing specialized tasks with progress streaming.
    """

    def __init__(
        self,
        llm_provider: str = "openai",
        model: str | None = None,
        enabled_toolkits: list[str] | None = None,
        permissions: dict | None = None,
        working_directory: str | None = None,
        **kwargs
    ):
        super().__init__(llm_provider=llm_provider, model=model, **kwargs)

        self.enabled_toolkits = enabled_toolkits or []
        self.permissions = permissions or {}
        self._working_directory = working_directory
        self._tool_helper: ToolHelper | None = None

        # Build the workflow graph
        self.graph = self._build_graph()

    @classmethod
    def get_descriptor(cls) -> SubagentDescriptor:
        """Return agent metadata for discovery and routing."""
        return SubagentDescriptor(
            subagent_id="my-agent",
            display_name="My Agent",
            description="Performs specialized tasks with web search and analysis",
            backend_type="INPROC",
            task_types=["research", "analysis"],
            keywords=["research", "search", "analyze", "investigate"],
            requires_explicit_command=False,
            supports_streaming=True,
            supports_parallel_invocation=False,
            max_concurrency=1,
            cost_hint=CostHint.HIGH,
            latency_hint=LatencyHint.BATCH,
            input_schema=MyAgentInput.model_json_schema(),
            output_schema=MyAgentOutput.model_json_schema(),
            supports_hitl=False,
        )

    @override
    def get_state_class(self) -> Type:
        """Return the state class for this agent."""
        return MyAgentState

    def _build_graph(self) -> StateGraph:
        """Build the workflow graph with nodes and edges."""
        workflow = StateGraph(MyAgentState)

        # Add nodes
        workflow.add_node("analyze_query", self._analyze_query_node)
        workflow.add_node("search", self._search_node)
        workflow.add_node("synthesize", self._synthesize_node)

        # Define edges
        workflow.add_edge(START, "analyze_query")
        workflow.add_edge("analyze_query", "search")
        workflow.add_edge("search", "synthesize")
        workflow.add_edge("synthesize", END)

        return workflow.compile()

    async def _ensure_tool_helper(self) -> ToolHelper:
        """Get or create tool helper."""
        if self._tool_helper is None:
            self._tool_helper = await create_tool_helper(
                agent_id=self.agent_id,
                enabled_toolkits=self.enabled_toolkits,
                permissions=self.permissions,
                working_directory=self._working_directory,
            )
        return self._tool_helper

    async def _analyze_query_node(self, state: MyAgentState) -> dict:
        """Analyze the user query to determine approach."""
        # This method is called by LangGraph during execution
        # Return state updates as dict

        query = state["user_message"]

        # Use LLM for analysis
        # (This is simplified - see existing agents for full examples)
        analysis = await self.llm.ainvoke([
            {"role": "system", "content": "Analyze the query..."},
            {"role": "user", "content": query}
        ])

        return {
            "current_step": "analysis_complete",
            "findings": [f"Query type: {analysis.content}"]
        }

    async def _search_node(self, state: MyAgentState) -> dict:
        """Execute search using tools."""
        tool_helper = await self._ensure_tool_helper()

        # Call tools
        result = await tool_helper.call_tool(
            "web_search",
            {"query": state["user_message"]}
        )

        return {
            "current_step": "search_complete",
            "findings": [result]
        }

    async def _synthesize_node(self, state: MyAgentState) -> dict:
        """Synthesize final result."""
        findings = state.get("findings", [])

        # Generate final result
        final = await self.llm.ainvoke([
            {"role": "system", "content": "Synthesize findings..."},
            {"role": "user", "content": str(findings)}
        ])

        return {
            "final_result": final.content,
            "current_step": "complete"
        }

    async def run(
        self,
        user_message: str,
        context: dict | None = None,
        config: dict | None = None
    ) -> str:
        """
        Main entry point for synchronous execution.

        Returns final result as string.
        """
        context = context or {}
        config = config or {}

        initial_state = {
            "user_message": user_message,
            "context": context,
            "findings": [],
            "current_step": "initialized",
            "final_result": None,
            "errors": [],
        }

        result_state = await self.graph.ainvoke(initial_state, config)
        return result_state.get("final_result", "No result produced")

    async def astream_progress(
        self,
        user_message: str,
        context: dict | None = None,
        config: dict | None = None
    ) -> AsyncGenerator[ProgressEvent, None]:
        """
        Stream progress events during execution.

        This is the key method for real-time feedback.
        """
        context = context or {}
        config = config or {}
        session_id = str(uuid.uuid7())

        # Session start event
        yield ProgressEvent(
            type=ProgressEventType.SESSION_START,
            session_id=session_id,
            data={"user_message": user_message}
        )

        initial_state = {
            "user_message": user_message,
            "context": context,
            "findings": [],
            "current_step": "initialized",
            "final_result": None,
            "errors": [],
        }

        # Stream graph execution
        async for event in self.graph.astream(initial_state, config):
            for node_name, node_output in event.items():
                # Emit step start
                yield ProgressEvent(
                    type=ProgressEventType.STEP_START,
                    session_id=session_id,
                    data={"step": node_name}
                )

                # Emit thinking event
                yield ProgressEvent(
                    type=ProgressEventType.THINKING,
                    session_id=session_id,
                    data={"thought": f"Executing {node_name}"}
                )

                # Emit tool events if applicable
                if node_name == "search":
                    yield ProgressEvent(
                        type=ProgressEventType.TOOL_START,
                        session_id=session_id,
                        data={"tool": "web_search"}
                    )

                # Emit step complete
                yield ProgressEvent(
                    type=ProgressEventType.STEP_COMPLETE,
                    session_id=session_id,
                    data={"step": node_name, "output": node_output}
                )

        # Session end event
        yield ProgressEvent(
            type=ProgressEventType.SESSION_END,
            session_id=session_id,
            data={"status": "completed"}
        )

    # Optional: Implement SubagentProtocol methods for full integration

    async def initialize(self, context: SubagentContext) -> None:
        """Initialize agent with context."""
        self._context = context

    async def shutdown(self) -> None:
        """Cleanup resources."""
        if self._tool_helper:
            await self._tool_helper.cleanup()
            self._tool_helper = None

    async def execute(
        self,
        task: str,
        **kwargs
    ) -> AsyncGenerator[SubagentProgressEvent, None]:
        """Execute task with subagent progress events."""
        # Convert to SubagentProgressEvent format
        async for event in self.astream_progress(task, kwargs):
            yield SubagentProgressEvent.from_progress_event(event)
```

### 6. Create `__init__.py` Exports

```python
"""My Agent - Specialized task agent."""

from .agent import MyAgent
from .schemas import MyAgentInput, MyAgentOutput

__all__ = ["MyAgent", "MyAgentInput", "MyAgentOutput"]
```

### 7. Register with SubagentManager

Add to `noesium/src/noesium/subagents/__init__.py`:

```python
from .my_agent import MyAgent

# Add to registry
SUBAGENTS = {
    "my-agent": MyAgent,
}
```

Or register dynamically:

```python
from noesium.core.agent.subagent.manager import SubagentManager
from noesium.core.agent.subagent.descriptor import SubagentRoutingPolicy
from my_agent import MyAgent

manager = SubagentManager()
manager.register(
    MyAgent,
    SubagentRoutingPolicy(
        keywords=["research", "search"],
        task_types=["research"],
        priority=1
    )
)
```

### 8. Create Prompts (Optional)

Create `prompts.py` for system prompts:

```python
SYSTEM_PROMPT = """You are a specialized research agent...

Your capabilities:
- Search the web for information
- Analyze and synthesize findings
- Provide structured outputs

Guidelines:
- Be thorough but concise
- Cite sources
- Indicate confidence levels
"""

ANALYSIS_PROMPT = """Analyze the following query...

Query: {query}

Provide:
1. Query type
2. Key concepts
3. Search strategy
"""
```

### 9. Create Custom Tools (Optional)

Create `tools.py` for agent-specific tools:

```python
from langchain_core.tools import tool

@tool
def analyze_sentiment(text: str) -> dict:
    """Analyze sentiment of text."""
    # Implementation
    return {"sentiment": "positive", "confidence": 0.95}

@tool
def extract_entities(text: str) -> list[dict]:
    """Extract named entities from text."""
    # Implementation
    return [{"entity": "Example", "type": "ORG"}]
```

### 10. Add Tests

Create tests in `tests/subagents/test_my_agent.py`:

```python
import pytest
from noesium.subagents.my_agent import MyAgent, MyAgentInput

@pytest.mark.asyncio
async def test_my_agent_basic():
    agent = MyAgent(llm_provider="openai")

    result = await agent.run("What is machine learning?")
    assert result is not None
    assert len(result) > 0

@pytest.mark.asyncio
async def test_my_agent_streaming():
    agent = MyAgent(llm_provider="openai")

    events = []
    async for event in agent.astream_progress("Test query"):
        events.append(event)

    assert len(events) > 0
    assert events[0].type == ProgressEventType.SESSION_START
    assert events[-1].type == ProgressEventType.SESSION_END

def test_descriptor():
    descriptor = MyAgent.get_descriptor()
    assert descriptor.subagent_id == "my-agent"
    assert descriptor.supports_streaming is True
```

## Progress Events Guide

### Core Event Types

Use these events for streaming:

```python
# Session lifecycle
ProgressEventType.SESSION_START
ProgressEventType.SESSION_END

# Step tracking
ProgressEventType.STEP_START
ProgressEventType.STEP_COMPLETE

# Tool execution
ProgressEventType.TOOL_START
ProgressEventType.TOOL_END

# Agent communication
ProgressEventType.THINKING
ProgressEventType.TEXT_CHUNK
ProgressEventType.FINAL_ANSWER

# Subagent events
ProgressEventType.SUBAGENT_START
ProgressEventType.SUBAGENT_PROGRESS
ProgressEventType.SUBAGENT_END

# Error handling
ProgressEventType.ERROR
```

### Event Pattern

```python
async def astream_progress(self, user_message, context, config):
    session_id = str(uuid.uuid7())

    # 1. Start session
    yield ProgressEvent(
        type=ProgressEventType.SESSION_START,
        session_id=session_id,
        data={"message": user_message}
    )

    # 2. Execute workflow with events
    async for event in self.graph.astream(initial_state):
        for node_name, node_output in event.items():
            # Step start
            yield ProgressEvent(
                type=ProgressEventType.STEP_START,
                session_id=session_id,
                data={"step": node_name}
            )

            # Thinking
            yield ProgressEvent(
                type=ProgressEventType.THINKING,
                session_id=session_id,
                data={"thought": f"Processing {node_name}"}
            )

            # Tool calls
            if "tool_calls" in node_output:
                for tool_call in node_output["tool_calls"]:
                    yield ProgressEvent(
                        type=ProgressEventType.TOOL_START,
                        session_id=session_id,
                        data={"tool": tool_call["name"]}
                    )

            # Step complete
            yield ProgressEvent(
                type=ProgressEventType.STEP_COMPLETE,
                session_id=session_id,
                data={"step": node_name, "result": node_output}
            )

    # 3. End session
    yield ProgressEvent(
        type=ProgressEventType.SESSION_END,
        session_id=session_id,
        data={"status": "completed"}
    )
```

## Examples from Existing Subagents

### ExploreAgent (noesium/subagents/explore/)

**Purpose**: Gather information from files, documents, and data
**Key Features**:
- Multi-source exploration (files, web, databases)
- Iterative refinement
- Structured output with findings

**Pattern**: `noesium/src/noesium/subagents/explore/agent.py:1`

### PlanAgent (noesium/subagents/plan/)

**Purpose**: Create structured implementation plans
**Key Features**:
- Domain-agnostic planning
- Step decomposition
- Dependency tracking

**Pattern**: `noesium/src/noesium/subagents/plan/agent.py:1`

### TacitusAgent (noesium/subagents/tacitus/)

**Purpose**: Research with iterative query generation
**Key Features**:
- Web search integration
- Query refinement
- Citation tracking

**Pattern**: `noesium/src/noesium/subagents/tacitus/agent.py:1`

## Common Patterns

### Conditional Edges in Workflow

```python
def _build_graph(self) -> StateGraph:
    workflow = StateGraph(MyAgentState)

    workflow.add_node("analyze", self._analyze_node)
    workflow.add_node("search", self._search_node)
    workflow.add_node("skip", self._skip_node)

    workflow.add_edge(START, "analyze")
    workflow.add_conditional_edges(
        "analyze",
        self._should_search,
        {
            "search": "search",
            "skip": "skip"
        }
    )

    return workflow.compile()

def _should_search(self, state: MyAgentState) -> str:
    """Determine next step based on state."""
    if state.get("needs_search"):
        return "search"
    return "skip"
```

### Tool Integration

```python
async def _execute_with_tools(self, state: MyAgentState) -> dict:
    tool_helper = await self._ensure_tool_helper()

    # List available tools
    tools = await tool_helper.list_tools()

    # Call a tool
    result = await tool_helper.call_tool(
        "web_search",
        {"query": "example query", "num_results": 5}
    )

    # Handle result
    if result.get("success"):
        return {"findings": result["results"]}
    else:
        return {"errors": [result.get("error")]}
```

### Error Handling

```python
async def _robust_node(self, state: MyAgentState) -> dict:
    try:
        # Attempt operation
        result = await self._risky_operation(state)
        return {"result": result}

    except Exception as e:
        # Log error in state
        return {
            "errors": [f"Failed: {str(e)}"],
            "current_step": "error"
        }
```

### State Checkpointing

```python
from langgraph.checkpoint.memory import MemorySaver

def _build_graph(self) -> StateGraph:
    workflow = StateGraph(MyAgentState)
    # ... add nodes and edges ...

    # Add checkpointing
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
```

## Common Issues

### Issue: Circular Imports

**Problem**: Import cycles between agent modules

**Solution**:
- Use lazy imports in `__init__.py`
- Restructure to avoid circular dependencies
- Use TYPE_CHECKING for type hints

```python
# In __init__.py
def __getattr__(name: str):
    if name == "MyAgent":
        from .agent import MyAgent
        return MyAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### Issue: State Not Updating

**Problem**: State fields not accumulating or updating

**Solution**:
- Use `Annotated[list, add]` for lists
- Return dict with updates, not full state
- Check LangGraph documentation for state reducers

### Issue: Progress Events Not Appearing

**Problem**: Events not streamed to client

**Solution**:
- Ensure `astream_progress()` yields events
- Check event types are correct
- Verify session_id is consistent

### Issue: Tool Access Denied

**Problem**: Tools not available or permission errors

**Solution**:
- Check `enabled_toolkits` in constructor
- Verify permissions dict includes needed permissions
- Ensure `ToolHelper` is properly initialized

## Advanced Features

### Human-in-the-Loop (HITL)

```python
async def _request_approval(self, state: MyAgentState) -> dict:
    # Yield HITL request event
    yield SubagentProgressEvent.hitl_request(
        request_id=str(uuid.uuid7()),
        prompt="Should I proceed with this action?",
        options=["approve", "reject", "modify"],
        context=state
    )

    # Wait for response
    response = await self._wait_for_hitl_response()

    return {"approved": response.choice == "approve"}
```

### Parallel Execution

```python
async def _parallel_search(self, state: MyAgentState) -> dict:
    queries = state["search_queries"]

    # Execute in parallel
    tasks = [
        self._search_one(query)
        for query in queries
    ]

    results = await asyncio.gather(*tasks)

    return {"findings": results}
```

### Memory and Context

```python
async def initialize(self, context: SubagentContext) -> None:
    """Load memory from context."""
    self._context = context
    self._memory = await context.get_memory()

    # Access previous sessions
    self._history = await context.get_history(limit=5)

async def shutdown(self) -> None:
    """Save memory to context."""
    if self._context:
        await self._context.save_memory(self._memory)
```

## Validation Checklist

Before finalizing your subagent:

- [ ] Inherits from `BaseGraphicAgent`
- [ ] Implements `get_state_class()` returning TypedDict
- [ ] Implements `_build_graph()` returning compiled StateGraph
- [ ] Implements `run()` for synchronous execution
- [ ] Implements `astream_progress()` for streaming events
- [ ] Returns correct event types from `ProgressEventType`
- [ ] `get_descriptor()` returns valid `SubagentDescriptor`
- [ ] State uses `Annotated[list, add]` for accumulators
- [ ] Error handling captures issues in state
- [ ] Tool access via `ToolHelper` with permissions
- [ ] Unit tests cover basic execution
- [ ] Unit tests cover streaming events
- [ ] `__init__.py` exports main classes
- [ ] Registered with `SubagentManager`
- [ ] Documentation in docstrings

## Related Files

- **Base classes**: `noesium/src/noesium/core/agent/base.py:1`
- **Subagent protocol**: `noesium/src/noesium/core/agent/subagent/protocol.py:1`
- **Progress events**: `noesium/src/noesium/core/event/progress.py:1`
- **Subagent events**: `noesium/src/noesium/core/agent/subagent/events.py:1`
- **Subagent manager**: `noesium/src/noesium/core/agent/subagent/manager.py:1`
- **Tool helper**: `noesium/src/noesium/core/tool/helper.py:1`

## Example: Minimal Subagent

```python
"""Minimal subagent example."""

from noesium.core.agent.base import BaseGraphicAgent
from noesium.core.agent.subagent.descriptor import SubagentDescriptor, CostHint, LatencyHint
from noesium.core.event import ProgressEvent, ProgressEventType
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

class MinimalState(TypedDict):
    message: str
    result: str | None

class MinimalAgent(BaseGraphicAgent):
    """Simple agent that processes messages."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.graph = self._build_graph()

    @classmethod
    def get_descriptor(cls) -> SubagentDescriptor:
        return SubagentDescriptor(
            subagent_id="minimal",
            display_name="Minimal Agent",
            description="Simple message processor",
            backend_type="INPROC",
            task_types=["simple"],
            keywords=["simple", "basic"],
            requires_explicit_command=False,
            supports_streaming=True,
            supports_parallel_invocation=True,
            max_concurrency=None,
            cost_hint=CostHint.LOW,
            latency_hint=LatencyHint.INTERACTIVE,
            input_schema={},
            output_schema={},
            supports_hitl=False,
        )

    def get_state_class(self) -> type:
        return MinimalState

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(MinimalState)
        workflow.add_node("process", self._process_node)
        workflow.add_edge(START, "process")
        workflow.add_edge("process", END)
        return workflow.compile()

    async def _process_node(self, state: MinimalState) -> dict:
        result = f"Processed: {state['message']}"
        return {"result": result}

    async def run(self, message: str, **kwargs) -> str:
        result = await self.graph.ainvoke({"message": message, "result": None})
        return result["result"]

    async def astream_progress(self, message: str, **kwargs):
        import uuid
        session_id = str(uuid.uuid7())

        yield ProgressEvent(type=ProgressEventType.SESSION_START, session_id=session_id)
        result = await self.run(message)
        yield ProgressEvent(type=ProgressEventType.FINAL_ANSWER, session_id=session_id, data={"result": result})
        yield ProgressEvent(type=ProgressEventType.SESSION_END, session_id=session_id)
```

## Next Steps

After creating your subagent:

1. **Test thoroughly** with various inputs
2. **Add to documentation** in main README
3. **Create usage examples** for common scenarios
4. **Monitor performance** in production
5. **Gather feedback** from users
6. **Iterate and improve** based on usage patterns