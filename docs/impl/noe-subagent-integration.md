# NoeAgent ↔ Built-in Subagent Progress Integration

> Detailed design for exposing BrowserUseAgent, TacitusAgent, and other built-in subagent progress 
> to NoeAgent TUI with real-time visibility.

**Status**: Draft  
**Created**: 2026-03-03  
**Related**: `noeagent-tui-analysis.md`, `RFC-1004`, `RFC-1005`

---

## Executive Summary

This document describes the design for exposing detailed progress of built-in subagents 
(BrowserUseAgent, TacitusAgent) to NoeAgent's TUI, enabling users to observe real-time 
browser actions, research queries, and other subagent activities.

---

## 1. Current Architecture Analysis

### 1.1 Event Flow Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Current Event Flow                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  NoeAgent.astream_progress()                                                │
│       │                                                                      │
│       ├──► ProgressEvent (SESSION_START)                                    │
│       ├──► ProgressEvent (PLAN_CREATED)                                     │
│       ├──► ProgressEvent (STEP_START)                                       │
│       │    │                                                                 │
│       │    ├──► BuiltInAgentCapabilityProvider.invoke()                     │
│       │    │    │                                                            │
│       │    │    └──► BrowserUseAgent.run() ◄── BLOCKING, NO EVENTS          │
│       │    │         │                                                       │
│       │    │         └──► returns AgentHistoryList                          │
│       │    │                                                                │
│       │    └──► (TUI shows nothing during browser execution)                │
│       │                                                                      │
│       ├──► ProgressEvent (TOOL_END) ◄── Only shows final result             │
│       └──► ProgressEvent (FINAL_ANSWER)                                     │
│                                                                              │
│  GAP: No intermediate progress from built-in subagents!                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Analysis

#### NoeAgent ([agent.py](../../noesium/noeagent/agent.py))

| Component | Status | Notes |
|-----------|--------|-------|
| `astream_progress()` | ✅ Complete | Yields `ProgressEvent` for all internal events |
| `_subagent_event_queue` | ✅ Present | `asyncio.Queue` for subagent events (line 83) |
| `interact_with_subagent()` | ✅ Streams | For child NoeAgent spawning, wraps events properly |
| `_setup_builtin_subagents()` | ✅ Registers | Creates `BuiltInAgentCapabilityProvider` |

#### BuiltInAgentCapabilityProvider ([providers.py:275-361](../../noesium/core/capability/providers.py#L275-L361))

| Method | Status | Notes |
|--------|--------|-------|
| `invoke()` | ⚠️ Blocking | Returns only final result, no progress |
| `invoke_streaming()` | ❌ Missing | Not implemented |

#### BrowserUseAgent ([agent/__init__.py](../../noesium/subagents/bu/agent/__init__.py))

| Component | Status | Notes |
|-----------|--------|-------|
| `run()` | ⚠️ Blocking | Returns `AgentHistoryList`, no streaming |
| `astream_progress()` | ❌ Missing | Not implemented |
| Internal `eventbus` | ✅ Present | `bubus.EventBus` for browser events |

#### TacitusAgent ([tacitus/agent.py](../../noesium/subagents/tacitus/agent.py))

| Component | Status | Notes |
|-----------|--------|-------|
| `research()` | ⚠️ Blocking | Returns `ResearchOutput`, no streaming |
| `astream_progress()` | ❌ Missing | Not implemented |
| LangGraph graph | ✅ Present | Has `_generate_query_node`, `_research_node`, etc. |

### 1.3 Event Type Coverage

| Event Type | NoeAgent Emits | BrowserUseAgent | TacitusAgent |
|------------|----------------|-----------------|--------------|
| `SESSION_START` | ✅ | ❌ | ❌ |
| `PLAN_CREATED` | ✅ | ❌ | ❌ |
| `STEP_START` | ✅ | ❌ | ❌ |
| `STEP_COMPLETE` | ✅ | ❌ | ❌ |
| `TOOL_START` | ✅ | ❌ | ❌ |
| `TOOL_END` | ✅ | ❌ | ❌ |
| `SUBAGENT_START` | ✅ (from kwargs) | ❌ | ❌ |
| `SUBAGENT_PROGRESS` | ⚠️ (never emitted) | ❌ | ❌ |
| `SUBAGENT_END` | ⚠️ (never emitted) | ❌ | ❌ |
| `THINKING` | ✅ | ❌ | ❌ |
| `FINAL_ANSWER` | ✅ | ❌ | ❌ |
| `ERROR` | ✅ | ❌ | ❌ |

---

## 2. Gap Analysis

### 2.1 Primary Gap: Built-in Subagent Opacity

**Problem**: When NoeAgent delegates to BrowserUseAgent or TacitusAgent, the TUI shows:

```
  [>] Step 2: Browse to example.com
    → Using browser_use(task="navigate to example.com")
    ⠋ Working on task... [browser_use]
    
    ... 30 seconds of silence ...
    
  [✓] Step 2: Browse to example.com
```

**Impact**: Users cannot see:
- Which page the browser is navigating to
- What elements are being clicked
- What content is being extracted
- When downloads occur
- Research queries being generated
- Web search results being processed

### 2.2 Secondary Gaps

1. **No Progress Protocol**: Built-in agents don't implement `astream_progress()`
2. **Blocking Provider**: `BuiltInAgentCapabilityProvider.invoke()` doesn't stream
3. **Event Translation Missing**: Browser events (`bubus.EventBus`) not translated to `ProgressEvent`
4. **TUI Handler Incomplete**: `SubagentTracker` exists but never receives browser-specific events

---

## 3. Target Architecture

### 3.1 Event Flow (After Implementation)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Target Event Flow                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  NoeAgent.astream_progress()                                                │
│       │                                                                      │
│       ├──► ProgressEvent (SESSION_START)                                    │
│       ├──► ProgressEvent (PLAN_CREATED)                                     │
│       ├──► ProgressEvent (STEP_START)                                       │
│       │    │                                                                 │
│       │    ├──► BuiltInAgentCapabilityProvider.invoke_streaming()           │
│       │    │    │                                                            │
│       │    │    └──► BrowserUseAgent.astream_progress()                     │
│       │    │         │                                                       │
│       │    │         ├──► ProgressEvent (SESSION_START)                     │
│       │    │         │    └── wrapped as SUBAGENT_PROGRESS                  │
│       │    │         │                                                       │
│       │    │         ├──► ProgressEvent (STEP_START)                        │
│       │    │         │    └── "→ Navigating to example.com"                 │
│       │    │         │                                                       │
│       │    │         ├──► ProgressEvent (TOOL_START)                        │
│       │    │         │    └── "👆 Clicking login button"                    │
│       │    │         │                                                       │
│       │    │         ├──► ProgressEvent (TOOL_END)                          │
│       │    │         │    └── "✓ Form submitted"                            │
│       │    │         │                                                       │
│       │    │         └──► ProgressEvent (FINAL_ANSWER)                      │
│       │    │              └── wrapped as SUBAGENT_END                       │
│       │    │                                                                │
│       │    └──► TUI shows real-time browser actions                         │
│       │                                                                      │
│       └──► ProgressEvent (FINAL_ANSWER)                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| `BrowserUseAgent.astream_progress()` | Yield `ProgressEvent` for each browser step/action |
| `TacitusAgent.astream_progress()` | Yield `ProgressEvent` for research phases |
| `BuiltInAgentCapabilityProvider.invoke_streaming()` | Stream wrapped events to parent |
| `NoeAgent._execute_builtin_subagent()` | Bridge streaming events to TUI |
| `SubagentTracker` | Display browser/research-specific progress |

---

## 4. Detailed Design

### 4.1 Progress Protocol Interface

All built-in subagents should implement this interface:

```python
from typing import AsyncGenerator, Protocol
from noesium.noeagent.progress import ProgressEvent

class ProgressStreamingAgent(Protocol):
    """Protocol for agents that stream progress events."""
    
    async def astream_progress(
        self,
        message: str,
        **kwargs,
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Stream progress events during execution.
        
        Yields:
            ProgressEvent: Events describing agent progress
            
        Event Requirements:
            - First event MUST be SESSION_START
            - Last event MUST be FINAL_ANSWER or ERROR
            - All events SHOULD have meaningful summary for TUI display
        """
        ...
```

### 4.2 BrowserUseAgent Progress Streaming

**File**: `noesium/subagents/bu/agent/__init__.py`

```python
from typing import AsyncGenerator
from noesium.noeagent.progress import ProgressEvent, ProgressEventType

class BrowserUseAgent(BaseAgent, Generic[T]):
    
    async def astream_progress(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        config: Any = None,
        max_steps: int = 25,
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Stream progress events during browser automation.
        
        Event Sequence:
            1. SESSION_START - Browser session initialized
            2. PLAN_CREATED - Dynamic plan (max_steps)
            3. STEP_START/STEP_COMPLETE - For each browser action
            4. TOOL_START/TOOL_END - For specific actions (click, type, etc.)
            5. FINAL_ANSWER - Task result
            6. SESSION_END - Cleanup complete
        """
        from uuid_extensions import uuid7str
        
        session_id = uuid7str()
        step_count = 0
        
        # Create underlying agent with step callback
        async def on_step(browser_state, model_output, step_num):
            nonlocal step_count
            step_count = step_num
        
        # Yield SESSION_START
        yield ProgressEvent(
            type=ProgressEventType.SESSION_START,
            session_id=session_id,
            summary=f"Browser task: {user_message[:60]}",
        )
        
        # Create agent instance
        from ..adapters.llm_adapter import BaseChatModel
        agent = Agent(
            task=user_message,
            llm=BaseChatModel(self._llm_client),
            browser_profile=self.browser_profile,
            use_vision=self.use_vision,
            register_new_step_callback=on_step,
        )
        
        # Yield PLAN_CREATED (browser steps are dynamic)
        yield ProgressEvent(
            type=ProgressEventType.PLAN_CREATED,
            session_id=session_id,
            summary=f"Browser automation: up to {max_steps} steps",
            plan_snapshot={
                "steps": [],
                "goal": user_message,
                "max_steps": max_steps,
            },
        )
        
        try:
            # Run with progress tracking
            result = await agent.run(max_steps=max_steps)
            
            # Yield events for completed steps
            for i, history_item in enumerate(result.history):
                # Step start
                yield ProgressEvent(
                    type=ProgressEventType.STEP_START,
                    session_id=session_id,
                    step_index=i,
                    summary=f"Browser step {i+1}",
                )
                
                # Extract action details from history
                if hasattr(history_item, 'model_output') and history_item.model_output:
                    action = history_item.model_output.action
                    if action:
                        action_desc = self._describe_action(action)
                        yield ProgressEvent(
                            type=ProgressEventType.TOOL_START,
                            session_id=session_id,
                            tool_name="browser_action",
                            summary=action_desc,
                            detail=str(action)[:500],
                        )
                
                # Step complete
                yield ProgressEvent(
                    type=ProgressEventType.STEP_COMPLETE,
                    session_id=session_id,
                    step_index=i,
                    summary=f"Step {i+1} completed",
                )
            
            # Yield final answer
            final_result = result.final_result()
            if final_result:
                yield ProgressEvent(
                    type=ProgressEventType.FINAL_ANSWER,
                    session_id=session_id,
                    text=final_result,
                    summary="Browser task completed",
                )
            
            self._last_result = result
            
        except Exception as e:
            yield ProgressEvent(
                type=ProgressEventType.ERROR,
                session_id=session_id,
                error=str(e),
                summary=f"Browser task failed: {e}",
            )
            raise
        
        finally:
            yield ProgressEvent(
                type=ProgressEventType.SESSION_END,
                session_id=session_id,
            )
    
    def _describe_action(self, action) -> str:
        """Generate human-readable description of browser action."""
        # Map action types to descriptions
        action_descriptions = {
            "click": "👆 Clicking element",
            "input_text": "⌨️ Typing text",
            "go_to_url": "→ Navigating to URL",
            "scroll": "📜 Scrolling page",
            "extract_content": "📄 Extracting content",
            "download_file": "📥 Downloading file",
            "switch_tab": "🔄 Switching tab",
            "done": "✓ Task complete",
        }
        
        action_name = type(action).__name__.lower()
        for key, desc in action_descriptions.items():
            if key in action_name:
                # Add context if available
                if hasattr(action, 'url'):
                    return f"{desc}: {action.url[:40]}"
                if hasattr(action, 'index'):
                    return f"{desc} at index {action.index}"
                return desc
        
        return f"🔧 Browser action: {action_name}"
```

### 4.3 TacitusAgent Progress Streaming

**File**: `noesium/subagents/tacitus/agent.py`

```python
from typing import AsyncGenerator
from noesium.noeagent.progress import ProgressEvent, ProgressEventType

class TacitusAgent(BaseResearcher):
    
    async def astream_progress(
        self,
        user_message: str,
        context: Dict[str, Any] = None,
        config: Optional[RunnableConfig] = None,
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Stream progress events during research.
        
        Event Sequence:
            1. SESSION_START - Research initiated
            2. PLAN_CREATED - Research plan (queries to generate)
            3. STEP_START - For each query generation
            4. TOOL_START/TOOL_END - For web searches
            5. THINKING - During reflection
            6. FINAL_ANSWER - Research summary
            7. SESSION_END - Complete
        """
        from uuid_extensions import uuid7str
        from langchain_core.messages import HumanMessage
        
        session_id = uuid7str()
        
        # Yield SESSION_START
        yield ProgressEvent(
            type=ProgressEventType.SESSION_START,
            session_id=session_id,
            summary=f"Research: {user_message[:60]}",
        )
        
        # Initialize state
        initial_state = {
            "messages": [HumanMessage(content=user_message)],
            "context": context,
            "search_query": [],
            "web_research_result": [],
            "sources_gathered": [],
            "initial_search_query_count": self.number_of_initial_queries,
            "max_research_loops": self.max_research_loops,
            "research_loop_count": 0,
        }
        
        try:
            # Stream graph execution
            current_loop = 0
            queries_generated = 0
            
            async for event in self.graph.astream(initial_state):
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue
                    
                    # Generate query node
                    if node_name == "generate_query":
                        query_list = node_output.get("query_list", [])
                        queries_generated = len(query_list)
                        
                        yield ProgressEvent(
                            type=ProgressEventType.PLAN_CREATED,
                            session_id=session_id,
                            summary=f"Generated {queries_generated} search queries",
                            plan_snapshot={
                                "steps": [
                                    {"description": f"Search: {q['query']}", "status": "pending"}
                                    for q in query_list
                                ],
                                "goal": user_message,
                            },
                        )
                        
                        for i, q in enumerate(query_list):
                            yield ProgressEvent(
                                type=ProgressEventType.STEP_START,
                                session_id=session_id,
                                step_index=i,
                                summary=f"Searching: {q['query'][:50]}",
                            )
                    
                    # Web research node
                    elif node_name == "web_research":
                        search_query = node_output.get("search_query", [])
                        sources = node_output.get("sources_gathered", [])
                        
                        for query in search_query:
                            yield ProgressEvent(
                                type=ProgressEventType.TOOL_START,
                                session_id=session_id,
                                tool_name="web_search",
                                summary=f"🔍 Searching: {query[:50]}",
                            )
                        
                        if sources:
                            yield ProgressEvent(
                                type=ProgressEventType.TOOL_END,
                                session_id=session_id,
                                tool_name="web_search",
                                tool_result=f"Found {len(sources)} sources",
                                summary=f"✓ Found {len(sources)} sources",
                            )
                        
                        for i in range(len(search_query)):
                            yield ProgressEvent(
                                type=ProgressEventType.STEP_COMPLETE,
                                session_id=session_id,
                                step_index=i,
                            )
                    
                    # Reflection node
                    elif node_name == "reflection":
                        is_sufficient = node_output.get("is_sufficient", False)
                        current_loop = node_output.get("research_loop_count", 0)
                        
                        yield ProgressEvent(
                            type=ProgressEventType.THINKING,
                            session_id=session_id,
                            summary="Reflecting on research results...",
                        )
                        
                        if not is_sufficient and current_loop < self.max_research_loops:
                            yield ProgressEvent(
                                type=ProgressEventType.PLAN_REVISED,
                                session_id=session_id,
                                summary=f"Need more research (loop {current_loop}/{self.max_research_loops})",
                            )
                    
                    # Finalize answer node
                    elif node_name == "finalize_answer":
                        messages = node_output.get("messages", [])
                        final_message = None
                        for msg in reversed(messages):
                            if hasattr(msg, 'content'):
                                final_message = msg.content
                                break
                        
                        sources = node_output.get("sources_gathered", [])
                        
                        yield ProgressEvent(
                            type=ProgressEventType.FINAL_ANSWER,
                            session_id=session_id,
                            text=final_message or "Research completed",
                            summary=f"Research complete ({len(sources)} sources)",
                            detail=f"Sources: {[s.get('url', s.get('title', 'unknown')) for s in sources[:5]]}",
                        )
            
        except Exception as e:
            yield ProgressEvent(
                type=ProgressEventType.ERROR,
                session_id=session_id,
                error=str(e),
                summary=f"Research failed: {e}",
            )
            raise
        
        finally:
            yield ProgressEvent(
                type=ProgressEventType.SESSION_END,
                session_id=session_id,
            )
```

### 4.4 BuiltInAgentCapabilityProvider Streaming

**File**: `noesium/core/capability/providers.py`

```python
from typing import AsyncGenerator

class BuiltInAgentCapabilityProvider:
    """Wraps a built-in subagent with progress streaming support."""
    
    async def invoke_streaming(
        self,
        message: str,
        **kwargs,
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Invoke the built-in agent with progress streaming.
        
        Wraps all child events as SUBAGENT_PROGRESS with proper metadata.
        """
        if self._agent_instance is None:
            self._agent_instance = self._agent_factory()
        
        # Check for astream_progress support
        if hasattr(self._agent_instance, "astream_progress"):
            async for event in self._agent_instance.astream_progress(message, **kwargs):
                # Skip SESSION_START/SESSION_END for wrapped events
                if event.type in (ProgressEventType.SESSION_START, ProgressEventType.SESSION_END):
                    continue
                
                # Wrap as SUBAGENT_PROGRESS
                wrapped = ProgressEvent(
                    type=ProgressEventType.SUBAGENT_PROGRESS,
                    session_id=event.session_id,
                    sequence=event.sequence,
                    subagent_id=self._name,
                    summary=f"[{self._name}] {event.summary or ''}",
                    detail=event.detail,
                    tool_name=event.tool_name,
                    tool_result=event.tool_result,
                    step_index=event.step_index,
                    step_desc=event.step_desc,
                    plan_snapshot=event.plan_snapshot,
                    metadata={
                        "child_event_type": event.type.value,
                        "agent_type": self._agent_type,
                        **(event.metadata or {}),
                    },
                )
                yield wrapped
            
            # Emit SUBAGENT_END
            yield ProgressEvent(
                type=ProgressEventType.SUBAGENT_END,
                subagent_id=self._name,
                summary=f"[{self._name}] completed",
            )
        else:
            # Fallback: emit start/end only
            yield ProgressEvent(
                type=ProgressEventType.SUBAGENT_START,
                subagent_id=self._name,
                summary=f"[{self._name}] started (no streaming)",
            )
            result = await self.invoke(message=message, **kwargs)
            yield ProgressEvent(
                type=ProgressEventType.SUBAGENT_END,
                subagent_id=self._name,
                summary=f"[{self._name}] completed",
                detail=str(result)[:500],
            )
```

### 4.5 NoeAgent Integration

**File**: `noesium/noeagent/agent.py`

Add method for streaming built-in subagent execution:

```python
class NoeAgent(BaseGraphicAgent):
    
    async def _execute_builtin_subagent_streaming(
        self,
        provider: "BuiltInAgentCapabilityProvider",
        message: str,
    ) -> str:
        """Execute built-in subagent with progress streaming to TUI.
        
        This method is called from subagent_node when handling invoke_builtin action.
        All progress events are forwarded to parent's callbacks and queued for
        astream_progress() to yield.
        """
        final_result = ""
        
        async for event in provider.invoke_streaming(message=message):
            # Fire to callbacks (SessionLogger, etc.)
            await self._fire_callbacks(event)
            
            # Queue for astream_progress to yield
            if self._subagent_event_queue is not None:
                self._subagent_event_queue.put_nowait(event)
            
            # Track final result
            if event.type == ProgressEventType.SUBAGENT_END:
                final_result = event.detail or event.summary or ""
        
        return final_result
```

Update `subagent_node` in `nodes.py`:

```python
async def subagent_node(
    state: AgentState,
    *,
    agent: Any,
) -> dict[str, Any]:
    """Handle subagent spawn/interact requests with streaming support."""
    
    elif sa.action == "invoke_builtin":
        registry = getattr(agent, "_registry", None)
        if registry is None:
            result = "Capability registry not configured."
        else:
            try:
                cap_id = f"builtin_agent:{sa.name}"
                provider = registry.get_by_name(cap_id)
                
                # Use streaming if available
                if hasattr(provider, "invoke_streaming"):
                    result = await agent._execute_builtin_subagent_streaming(
                        provider, sa.message
                    )
                else:
                    result = await provider.invoke(message=sa.message)
            except Exception as exc:
                result = f"Failed to invoke built-in agent '{sa.name}': {exc}"
    
    # ... rest of function ...
```

### 4.6 TUI Display Enhancements

**File**: `noesium/noeagent/tui.py`

The `SubagentTracker` already handles browser-specific events. Add action type icons:

```python
# Action type to icon mapping
BROWSER_ACTION_ICONS = {
    "go_to_url": "→",
    "click": "👆", 
    "input_text": "⌨️",
    "scroll": "📜",
    "extract_content": "📄",
    "download_file": "📥",
    "switch_tab": "🔄",
    "done": "✓",
}

RESEARCH_ACTION_ICONS = {
    "query_generation": "🔍",
    "web_search": "🔎",
    "reflection": "💭",
    "answer_synthesis": "📝",
}

def _activity_line(event: ProgressEvent, thinking_gen: DynamicThinkingText | None = None) -> Text | None:
    """Enhanced activity line with action-specific icons."""
    
    if etype == ProgressEventType.SUBAGENT_PROGRESS:
        tag = event.subagent_id or "subagent"
        child_type = (event.metadata or {}).get("child_event_type", "")
        agent_type = (event.metadata or {}).get("agent_type", "")
        
        # Get icon based on agent type and event
        icon = ""
        if agent_type == "browser_use":
            icon = BROWSER_ACTION_ICONS.get(child_type, "")
        elif agent_type == "tacitus":
            icon = RESEARCH_ACTION_ICONS.get(child_type, "")
        
        summary = event.summary or ""
        if summary.startswith(f"[{tag}]"):
            summary = summary[len(f"[{tag}]"):].strip()
        
        return Text.assemble(
            ("  ", ""),
            (f"[{tag}] ", "magenta"),
            (f"{icon} " if icon else "", ""),
            (summary, "dim"),
        )
```

---

## 5. Implementation Phases

### Phase 1: BrowserUseAgent Progress Streaming

**Files**: `noesium/subagents/bu/agent/__init__.py`

**Tasks**:
1. Add `astream_progress()` method to `BrowserUseAgent`
2. Implement action description helper `_describe_action()`
3. Map internal browser events to `ProgressEvent` types
4. Handle error cases with ERROR events

**Validation**: 
```python
async def test_browser_progress():
    agent = BrowserUseAgent()
    events = []
    async for event in agent.astream_progress("Navigate to example.com"):
        events.append(event)
    assert events[0].type == ProgressEventType.SESSION_START
    assert events[-1].type in (ProgressEventType.FINAL_ANSWER, ProgressEventType.ERROR)
```

### Phase 2: TacitusAgent Progress Streaming

**Files**: `noesium/subagents/tacitus/agent.py`

**Tasks**:
1. Add `astream_progress()` method to `TacitusAgent`
2. Stream LangGraph node outputs as progress events
3. Map research phases to appropriate event types
4. Include source counts in progress summaries

**Validation**:
```python
async def test_tacitus_progress():
    agent = TacitusAgent()
    events = []
    async for event in agent.astream_progress("Research AI agents"):
        events.append(event)
    assert any(e.type == ProgressEventType.PLAN_CREATED for e in events)
    assert events[-1].type == ProgressEventType.FINAL_ANSWER
```

### Phase 3: Provider Streaming Support

**Files**: `noesium/core/capability/providers.py`

**Tasks**:
1. Add `invoke_streaming()` method to `BuiltInAgentCapabilityProvider`
2. Implement event wrapping logic
3. Handle fallback for non-streaming agents
4. Add unit tests for the provider

**Validation**:
```python
async def test_provider_streaming():
    provider = BuiltInAgentCapabilityProvider(name="test", agent_factory=...)
    events = [e async for e in provider.invoke_streaming(message="test")]
    assert all(e.subagent_id == "test" for e in events)
```

### Phase 4: NoeAgent Integration

**Files**: `noesium/noeagent/agent.py`, `noesium/noeagent/nodes.py`

**Tasks**:
1. Add `_execute_builtin_subagent_streaming()` method
2. Update `subagent_node` to use streaming path
3. Ensure events flow to `_subagent_event_queue`
4. Update existing tests

**Validation**: Integration test with real browser task

### Phase 5: TUI Enhancements

**Files**: `noesium/noeagent/tui.py`

**Tasks**:
1. Add action-specific icons to `_activity_line()`
2. Enhance `SubagentTracker` for browser/research display
3. Add agent type to state tracking
4. Update display tests

**Validation**: Manual TUI testing with browser and research tasks

---

## 6. API Contract

### 6.1 Event Requirements

All built-in subagent `astream_progress()` implementations MUST:

1. **Yield SESSION_START** as the first event
2. **Yield FINAL_ANSWER or ERROR** as the last meaningful event
3. **Yield SESSION_END** as the final event
4. **Provide meaningful summaries** suitable for TUI display (< 80 chars)
5. **Include detail** for logging purposes

### 6.2 Event Flow Guarantee

```
SESSION_START
  ├── PLAN_CREATED (optional)
  ├── (STEP_START / STEP_COMPLETE)*
  ├── (TOOL_START / TOOL_END)*
  ├── THINKING (optional)
  ├── FINAL_ANSWER | ERROR
  └── SESSION_END
```

### 6.3 Metadata Conventions

| Field | Purpose | Example |
|-------|---------|---------|
| `agent_type` | Agent identifier | `"browser_use"`, `"tacitus"` |
| `child_event_type` | Original event type | `"tool.start"`, `"step.complete"` |
| `action_type` | Specific action | `"click"`, `"web_search"` |

---

## 7. Testing Strategy

### 7.1 Unit Tests

- `test_browser_agent_progress_events`: Verify event sequence
- `test_tacitus_agent_progress_events`: Verify research events
- `test_provider_streaming_wrapping`: Verify event wrapping
- `test_subagent_tracker_browser_events`: Verify TUI display

### 7.2 Integration Tests

- `test_noe_with_browser_subagent`: End-to-end with real browser
- `test_noe_with_tacitus_subagent`: End-to-end research task
- `test_parallel_subagent_progress`: Multiple concurrent subagents

### 7.3 Manual Testing

1. Run NoeAgent TUI: `noeagent`
2. Submit browser task: "Browse to example.com and extract the title"
3. Verify progress lines show navigation, extraction
4. Submit research task: "Research AI agents"
5. Verify query generation, search, reflection events

---

## 8. Backward Compatibility

### 8.1 Non-Streaming Agents

Agents without `astream_progress()` will:
- Emit `SUBAGENT_START` with "(no streaming)" note
- Execute via blocking `invoke()`
- Emit `SUBAGENT_END` with result

### 8.2 Existing Tests

All existing tests should pass without modification. The streaming path is additive.

---

## 9. Future Enhancements

1. **Parallel Subagent Execution**: Run multiple subagents concurrently with interleaved events
2. **Subagent Cancellation**: Cancel long-running browser tasks
3. **Progress Persistence**: Save progress to session logs for replay
4. **Custom Progress Handlers**: Allow users to define custom progress processors

---

## 10. References

- [NoeAgent TUI Analysis](./noeagent-tui-analysis.md)
- [RFC-1004: Capability Registry](../specs/RFC-1004.md)
- [RFC-1005: Progress Events](../specs/RFC-1005.md)
- [NoeAgent Implementation Guide](./noeagent-impl.md)
