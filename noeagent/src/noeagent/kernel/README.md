# Agent Kernel

The Agent Kernel is the reasoning engine that produces executable decisions (RFC-1005 Section 8).

## Overview

The Agent Kernel is one of the five core components of the NoeAgent Autonomous Architecture:

1. Goal Engine
2. Cognitive Loop
3. **Agent Kernel** (this component)
4. Capability System
5. Memory System

## Responsibilities

The Agent Kernel performs:

- **Reasoning**: Analyze goals and context to determine actions
- **Planning**: Decompose complex goals into executable steps
- **Tool Selection**: Choose appropriate tools from the Capability System
- **Subagent Invocation**: Delegate tasks to specialized subagents
- **Goal Updates**: Modify goal status based on execution progress

## Architecture

```
Cognitive Loop
      |
      v
Agent Kernel
      |
      +-- Reasoning Engine
      |        |
      |        v
      |   LLM-based Planning
      |
      +-- Decision Generator
               |
               v
          Decision Types:
          - tool_call
          - subagent_call
          - memory_update
          - goal_update
          - finish_goal
```

## Interface

The kernel exposes a simple step-based interface:

```python
async def step(goal: Goal, context: dict[str, Any]) -> Decision
```

### Parameters

- **goal**: The goal to reason about (from Goal Engine)
- **context**: Memory context projected for this goal

### Returns

A `Decision` object containing:

- `action`: Type of action to take (DecisionAction enum)
- `goal_id`: ID of the goal this decision relates to
- `reasoning`: Explanation of why this decision was made
- Action-specific parameters (tool_id, subagent_type, etc.)

## Decision Types

### 1. Tool Call

Execute a tool via the Capability System:

```python
Decision(
    action=DecisionAction.TOOL_CALL,
    goal_id=goal.id,
    tool_id="browser.search",
    tool_input={"query": "machine learning papers"},
)
```

### 2. Subagent Call

Delegate to a specialized subagent:

```python
Decision(
    action=DecisionAction.SUBAGENT_CALL,
    goal_id=goal.id,
    subagent_type="researcher",
    subagent_task="Analyze recent ML papers",
)
```

### 3. Memory Update

Store new information in memory:

```python
Decision(
    action=DecisionAction.MEMORY_UPDATE,
    goal_id=goal.id,
    memory_key="research/findings",
    memory_value={"topic": "ML", "papers": 42},
)
```

### 4. Goal Update

Modify goal status or properties:

```python
Decision(
    action=DecisionAction.GOAL_UPDATE,
    goal_id=goal.id,
    new_goal_status="blocked",
)
```

### 5. Finish Goal

Mark goal as completed:

```python
Decision(
    action=DecisionAction.FINISH_GOAL,
    goal_id=goal.id,
    reasoning="All tasks completed successfully",
)
```

## Integration with Cognitive Loop

The Agent Kernel is invoked by the Cognitive Loop during each tick:

```python
# In CognitiveLoop._tick()
goal = await self.goal_engine.next_goal()
context = await self._project_memory(goal)
decision = await self.agent_kernel.step(goal, context)
observation = await self._execute_decision(decision)
await self._update_memory(goal, observation)
```

The kernel's decision is executed by the Cognitive Loop, and the observation is stored in memory for future reasoning steps.

## Implementation Details

### Current Status

The AgentKernel is currently a wrapper around NoeAgent that provides the step-based interface. Future enhancements will include:

- Full integration with NoeAgent's planning and execution system
- ReAct-style multi-step reasoning
- Better prompt formulation from goals and context
- Decision validation against available capabilities
- Learning from execution observations

### Relationship to NoeAgent

The AgentKernel wraps a NoeAgent instance:

```python
class AgentKernel:
    def __init__(self, agent: NoeAgent):
        self._agent = agent

    async def step(self, goal: Goal, context: dict[str, Any]) -> Decision:
        # Use agent's LLM and planning capabilities
        # to produce a decision
```

This provides a clean abstraction between the Cognitive Loop and NoeAgent, allowing:

1. Clear separation of concerns
2. Easier testing and mocking
3. Future flexibility in reasoning implementations

## RFC Compliance

This component implements **RFC-1005 Section 8: Agent Kernel**.

Key requirements from the RFC:

- ✅ Provides reasoning engine for NoeAgent
- ✅ Performs cognitive reasoning and produces executable decisions
- ✅ Exposes `step(goal, context) -> decision` interface
- ✅ Supports all five decision types
- ✅ May perform multi-step reasoning internally

## Future Work

1. **Enhanced Reasoning**: Implement ReAct-style reasoning chains
2. **Decision Validation**: Validate decisions against capability registry
3. **Learning**: Adapt reasoning based on execution outcomes
4. **Parallel Planning**: Consider multiple action paths simultaneously
5. **Explainability**: Provide detailed reasoning traces

## References

- [RFC-1005: NoeAgent Autonomous Architecture](../../../docs/specs/RFC-1005.md)
- [RFC-1006: Goal Engine](../../../docs/specs/RFC-1006.md)
- [RFC-1002: Memory Projection Model](../../../docs/specs/RFC-1002.md)